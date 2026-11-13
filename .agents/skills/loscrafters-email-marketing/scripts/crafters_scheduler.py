#!/usr/bin/env python3
"""
Programador nativo de campañas B2B y monitor CRM en macOS (launchd) — Los Crafters SRL.

Reemplaza los temporizadores en memoria de sesiones de chat por LaunchAgents reales
del sistema operativo (`~/Library/LaunchAgents/`), garantizando ejecución puntual
al minuto exacto programado (StartCalendarInterval) incluso tras reinicios o
re-conexiones breves de red al despertar el equipo.
"""

import argparse
import csv
from datetime import datetime, timedelta
import fcntl
import json
import os
from pathlib import Path
import plistlib
import re
import socket
import subprocess
import sys
import time

SCRIPTS_DIR = Path(__file__).resolve().parent
MAILER_SCRIPT = SCRIPTS_DIR / "crafters_mailer.py"
JOBS_DIR = SCRIPTS_DIR / "scheduled_jobs"
LOGS_DIR = SCRIPTS_DIR / "logs"
LAUNCH_AGENTS_DIR = Path.home() / "Library" / "LaunchAgents"

CRM_LABEL = "com.loscrafters.crm-monitor"
CAMPAIGN_LABEL_PREFIX = "com.loscrafters.campaign."

sys.path.insert(0, str(SCRIPTS_DIR))
import crafters_mailer  # noqa: E402


def ensure_dirs() -> None:
    JOBS_DIR.mkdir(parents=True, exist_ok=True)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    LAUNCH_AGENTS_DIR.mkdir(parents=True, exist_ok=True)


def iso_now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def get_python_bin() -> str:
    return str(Path(sys.executable).resolve())


def get_gui_domain() -> str:
    return f"gui/{os.getuid()}"


def sanitize_slug(text: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_-]+", "_", text.strip().lower()).strip("_")
    return cleaned[:32] or "campana"


def count_valid_recipients(csv_path: Path) -> int:
    count = 0
    with open(csv_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            email_to = (row.get("correo") or "").strip()
            if email_to and "@" in email_to and "ejemplo-" not in email_to:
                count += 1
    return count


def wait_for_tcp(host: str, port: int, timeout_s: int = 180) -> bool:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, port), timeout=5):
                return True
        except OSError:
            time.sleep(3)
    return False


def launchctl_list_labels() -> set[str]:
    res = subprocess.run(["launchctl", "list"], capture_output=True, text=True)
    labels = set()
    if res.returncode == 0:
        for line in res.stdout.splitlines()[1:]:
            parts = line.split("\t")
            if len(parts) >= 3:
                labels.add(parts[2].strip())
    return labels


def launchctl_bootout(label: str) -> None:
    domain = get_gui_domain()
    subprocess.run(
        ["launchctl", "bootout", f"{domain}/{label}"],
        capture_output=True,
        text=True,
    )


def launchctl_bootstrap(plist_path: Path, label: str) -> None:
    domain = get_gui_domain()
    launchctl_bootout(label)
    res = subprocess.run(
        ["launchctl", "bootstrap", domain, str(plist_path)],
        capture_output=True,
        text=True,
    )
    if res.returncode != 0:
        err = (res.stderr or res.stdout or "").strip()
        raise RuntimeError(f"Error al registrar {label} en launchd: {err}")


def save_json_atomic(path: Path, payload: dict) -> None:
    tmp_path = path.with_suffix(".json.tmp")
    tmp_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp_path.replace(path)


def schedule_detached_bootout(label: str) -> None:
    """Descarga el job one-shot 1s después de salir para evitar SIGTERM prematuro sobre sí mismo."""
    domain = get_gui_domain()
    subprocess.Popen(
        [
            get_python_bin(),
            "-c",
            (
                "import subprocess, time; time.sleep(1.0); "
                f"subprocess.run(['launchctl', 'bootout', '{domain}/{label}'], "
                "stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)"
            ),
        ],
        start_new_session=True,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def cmd_schedule_campaign(args) -> int:
    ensure_dirs()
    try:
        target_dt = datetime.strptime(args.datetime, "%Y-%m-%d %H:%M")
    except ValueError:
        print("❌ Formato inválido en --datetime. Usa 'YYYY-MM-DD HH:MM' (ej. '2026-11-14 08:30').")
        return 1

    if target_dt <= datetime.now():
        print(f"❌ La fecha/hora {args.datetime} ya pasó. Indica una hora futura.")
        return 1

    csv_path = Path(args.csv).resolve()
    if not csv_path.exists():
        print(f"❌ No existe el CSV de prospectos: {csv_path}")
        return 1

    valid_count = count_valid_recipients(csv_path)
    if valid_count == 0:
        print(f"❌ El CSV {csv_path} no contiene destinatarios válidos.")
        return 1

    # Evitar duplicados idénticos activos (mismo horario + nicho + csv)
    for existing_file in JOBS_DIR.glob("*.json"):
        try:
            existing = json.loads(existing_file.read_text(encoding="utf-8"))
        except Exception:
            continue
        if (
            existing.get("status") == "scheduled"
            and existing.get("scheduled_for") == target_dt.strftime("%Y-%m-%d %H:%M")
            and existing.get("nicho") == args.nicho
            and existing.get("csv") == str(csv_path)
            and bool(existing.get("dry_run")) == bool(args.dry_run)
        ):
            print(
                f"⚠️ Ya existe un job programado idéntico: {existing['job_id']} "
                f"({existing['scheduled_for']}). No se creará duplicado."
            )
            return 0

    slug = sanitize_slug(args.name or args.nicho)
    if args.dry_run and not slug.startswith("dryrun"):
        slug = f"dryrun_{slug}"
    base_id = f"{target_dt.strftime('%Y%m%d_%H%M')}_{slug}"
    job_id = base_id
    counter = 2
    while (JOBS_DIR / f"{job_id}.json").exists():
        job_id = f"{base_id}_{counter}"
        counter += 1

    label = f"{CAMPAIGN_LABEL_PREFIX}{job_id}"
    plist_path = LAUNCH_AGENTS_DIR / f"{label}.plist"
    job_json_path = JOBS_DIR / f"{job_id}.json"
    job_log_path = LOGS_DIR / f"campaign_{job_id}.log"

    plist_data = {
        "Label": label,
        "ProgramArguments": [
            get_python_bin(),
            str(Path(__file__).resolve()),
            "--run-job",
            job_id,
        ],
        "WorkingDirectory": str(SCRIPTS_DIR),
        "StartCalendarInterval": {
            "Month": target_dt.month,
            "Day": target_dt.day,
            "Hour": target_dt.hour,
            "Minute": target_dt.minute,
        },
        "StandardOutPath": str(LOGS_DIR / f"campaign_{job_id}.launchd.stdout.log"),
        "StandardErrorPath": str(LOGS_DIR / f"campaign_{job_id}.launchd.stderr.log"),
        "RunAtLoad": False,
    }
    with open(plist_path, "wb") as pf:
        plistlib.dump(plist_data, pf)

    job_record = {
        "job_id": job_id,
        "label": label,
        "plist_path": str(plist_path),
        "nicho": args.nicho,
        "csv": str(csv_path),
        "valid_recipients": valid_count,
        "scheduled_for": target_dt.strftime("%Y-%m-%d %H:%M"),
        "scheduled_year": target_dt.year,
        "dry_run": bool(args.dry_run),
        "status": "scheduled",
        "created_at": iso_now(),
        "started_at": None,
        "finished_at": None,
        "exit_code": None,
        "error": None,
        "log_path": str(job_log_path),
    }
    save_json_atomic(job_json_path, job_record)

    try:
        launchctl_bootstrap(plist_path, label)
    except Exception as exc:
        plist_path.unlink(missing_ok=True)
        job_record["status"] = "failed_register"
        job_record["error"] = str(exc)
        save_json_atomic(job_json_path, job_record)
        print(f"❌ {exc}")
        return 1

    print(f"✅ Campaña programada nativamente en macOS launchd")
    print(f"   Job ID:        {job_id}")
    print(f"   Label:         {label}")
    print(f"   Ejecución:     {job_record['scheduled_for']} (hora local)")
    print(f"   Nicho / CSV:   {args.nicho} ({valid_count} destinatarios válidos) -> {csv_path.name}")
    print(f"   Modo:          {'DRY-RUN (solo preview, cero envíos)' if args.dry_run else 'PRODUCCIÓN (--send --notify)'}")
    print(f"   Plist:         {plist_path}")
    return 0


def append_log(log_path: Path, text: str) -> None:
    with open(log_path, "a", encoding="utf-8") as lf:
        lf.write(text)


def cmd_run_job(args) -> int:
    ensure_dirs()
    job_id = args.run_job
    job_json_path = JOBS_DIR / f"{job_id}.json"
    if not job_json_path.exists():
        print(f"❌ Job no encontrado: {job_json_path}")
        return 1

    lock_path = JOBS_DIR / f"{job_id}.lock"
    lock_file = open(lock_path, "w", encoding="utf-8")
    try:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print(f"⏳ Job {job_id} ya está en ejecución en otro proceso. Saliendo.")
        lock_file.close()
        return 0

    try:
        job = json.loads(job_json_path.read_text(encoding="utf-8"))
        label = job["label"]
        plist_path = Path(job["plist_path"])
        log_path = Path(job["log_path"])

        if job.get("status") in ("done", "running", "cancelled"):
            append_log(log_path, f"[{iso_now()}] Job {job_id} ignorado: estado actual='{job.get('status')}'.\n")
            plist_path.unlink(missing_ok=True)
            schedule_detached_bootout(label)
            return 0

        scheduled_year = int(job.get("scheduled_year", datetime.now().year))
        if scheduled_year != datetime.now().year:
            msg = f"Año programado ({scheduled_year}) no coincide con año actual ({datetime.now().year}). Omitiendo."
            append_log(log_path, f"[{iso_now()}] {msg}\n")
            job["status"] = "skipped_year_mismatch"
            job["error"] = msg
            save_json_atomic(job_json_path, job)
            plist_path.unlink(missing_ok=True)
            schedule_detached_bootout(label)
            return 0

        job["status"] = "running"
        job["started_at"] = iso_now()
        save_json_atomic(job_json_path, job)

        append_log(
            log_path,
            f"[{iso_now()}] === Inicio de job {job_id} (nicho={job['nicho']}, dry_run={job.get('dry_run')}) ===\n",
        )

        # Esperar red hasta 180s por si el Mac acaba de despertar
        if not wait_for_tcp("smtp.gmail.com", 465, timeout_s=180):
            err = "Sin conexión TCP a smtp.gmail.com:465 tras 180s de espera."
            append_log(log_path, f"[{iso_now()}] ❌ {err}\n")
            job["status"] = "failed_network"
            job["finished_at"] = iso_now()
            job["exit_code"] = 1
            job["error"] = err
            save_json_atomic(job_json_path, job)
            plist_path.unlink(missing_ok=True)
            schedule_detached_bootout(label)
            return 1

        if job.get("dry_run"):
            cmd = [
                get_python_bin(),
                str(MAILER_SCRIPT),
                "--preview",
                "--nicho",
                job["nicho"],
                "--csv",
                job["csv"],
            ]
        else:
            cmd = [
                get_python_bin(),
                str(MAILER_SCRIPT),
                "--send",
                "--nicho",
                job["nicho"],
                "--csv",
                job["csv"],
                "--notify",
            ]

        res = subprocess.run(cmd, capture_output=True, text=True, cwd=str(SCRIPTS_DIR))
        if res.stdout:
            append_log(log_path, res.stdout + ("\n" if not res.stdout.endswith("\n") else ""))
        if res.stderr:
            append_log(log_path, "[STDERR]\n" + res.stderr + ("\n" if not res.stderr.endswith("\n") else ""))

        job["finished_at"] = iso_now()
        job["exit_code"] = res.returncode
        if res.returncode == 0:
            job["status"] = "done"
            job["error"] = None
            if job.get("dry_run"):
                append_log(
                    log_path,
                    f"[{iso_now()}] ✅ DRY-RUN completado (archivo preview generado; cero correos reales enviados).\n",
                )
        else:
            job["status"] = "failed_execution"
            job["error"] = f"crafters_mailer terminó con código {res.returncode}"
            if not job.get("dry_run"):
                crafters_mailer.notify_phone(
                    "Error en campaña programada",
                    f"Job {job_id} ({job['nicho']}) falló con código {res.returncode}. Revisa {log_path.name}.",
                )

        append_log(log_path, f"[{iso_now()}] === Fin de job {job_id} (status={job['status']}) ===\n")
        save_json_atomic(job_json_path, job)

        # Limpiar LaunchAgent one-shot para que nunca vuelva a dispararse
        plist_path.unlink(missing_ok=True)
        schedule_detached_bootout(label)
        return res.returncode
    finally:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
        lock_file.close()


def cmd_install_crm_monitor(_args) -> int:
    ensure_dirs()
    intervals = [{"Hour": h, "Minute": m} for h in range(8, 24) for m in (0, 30)]
    plist_path = LAUNCH_AGENTS_DIR / f"{CRM_LABEL}.plist"
    plist_data = {
        "Label": CRM_LABEL,
        "ProgramArguments": [
            get_python_bin(),
            str(Path(__file__).resolve()),
            "--run-crm",
        ],
        "WorkingDirectory": str(SCRIPTS_DIR),
        "StartCalendarInterval": intervals,
        "StandardOutPath": str(LOGS_DIR / "crm_monitor.launchd.stdout.log"),
        "StandardErrorPath": str(LOGS_DIR / "crm_monitor.launchd.stderr.log"),
        "RunAtLoad": False,
    }
    with open(plist_path, "wb") as pf:
        plistlib.dump(plist_data, pf)

    try:
        launchctl_bootstrap(plist_path, CRM_LABEL)
    except Exception as exc:
        print(f"❌ {exc}")
        return 1

    print(f"✅ Monitor CRM nativo instalado en launchd: {CRM_LABEL}")
    print(f"   Ventana activa: 08:00 a 23:30 cada 30 min ({len(intervals)} disparos diarios)")
    print("   Silencio total: 00:00 a 07:59 (cero revisiones de madrugada)")
    print(f"   Plist:          {plist_path}")
    return 0


def cmd_uninstall_crm_monitor(_args) -> int:
    ensure_dirs()
    plist_path = LAUNCH_AGENTS_DIR / f"{CRM_LABEL}.plist"
    launchctl_bootout(CRM_LABEL)
    plist_path.unlink(missing_ok=True)
    print(f"🛑 Monitor CRM {CRM_LABEL} descargado y eliminado.")
    return 0


def rotate_log_if_large(log_path: Path, max_bytes: int = 512 * 1024) -> None:
    if log_path.exists() and log_path.stat().st_size > max_bytes:
        backup = log_path.with_suffix(log_path.suffix + ".1")
        backup.unlink(missing_ok=True)
        log_path.replace(backup)


def cmd_run_crm(_args) -> int:
    ensure_dirs()
    lock_path = LOGS_DIR / "crm_monitor.lock"
    lock_file = open(lock_path, "w", encoding="utf-8")
    try:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        lock_file.close()
        return 0

    log_path = LOGS_DIR / "crm_monitor.log"
    rotate_log_if_large(log_path)

    try:
        if not wait_for_tcp("imap.gmail.com", 993, timeout_s=30):
            append_log(log_path, f"[{iso_now()}] ⚠️ Sin conexión a imap.gmail.com:993; esperando próximo ciclo.\n")
            return 0

        res = subprocess.run(
            [get_python_bin(), str(MAILER_SCRIPT), "--crm", "--auto-reply"],
            capture_output=True,
            text=True,
            cwd=str(SCRIPTS_DIR),
        )
        append_log(log_path, f"[{iso_now()}] --- CRM Check (exit={res.returncode}) ---\n")
        if res.stdout:
            append_log(log_path, res.stdout + ("\n" if not res.stdout.endswith("\n") else ""))
        if res.stderr:
            append_log(log_path, "[STDERR]\n" + res.stderr + ("\n" if not res.stderr.endswith("\n") else ""))
        return res.returncode
    finally:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
        lock_file.close()


def cmd_cancel(args) -> int:
    ensure_dirs()
    job_id = args.cancel
    job_json_path = JOBS_DIR / f"{job_id}.json"
    label = f"{CAMPAIGN_LABEL_PREFIX}{job_id}"
    plist_path = LAUNCH_AGENTS_DIR / f"{label}.plist"

    launchctl_bootout(label)
    plist_path.unlink(missing_ok=True)

    if job_json_path.exists():
        job = json.loads(job_json_path.read_text(encoding="utf-8"))
        job["status"] = "cancelled"
        job["finished_at"] = iso_now()
        save_json_atomic(job_json_path, job)
        print(f"🛑 Job cancelado y eliminado de launchd: {job_id}")
    else:
        print(f"ℹ️ Se limpió launchd para {label} (no existía JSON previo).")
    return 0


def cmd_list(_args) -> int:
    ensure_dirs()
    loaded = launchctl_list_labels()
    crm_plist = LAUNCH_AGENTS_DIR / f"{CRM_LABEL}.plist"
    crm_state = "ACTIVO en launchd" if CRM_LABEL in loaded else "NO CARGADO"
    print(f"📡 Monitor CRM ({CRM_LABEL}): {crm_state} | Plist: {'sí' if crm_plist.exists() else 'no'}")
    print("-" * 72)

    job_files = sorted(JOBS_DIR.glob("*.json"))
    if not job_files:
        print("📭 No hay jobs de campaña registrados.")
        return 0

    print("📅 Campañas registradas:")
    for jf in job_files:
        try:
            job = json.loads(jf.read_text(encoding="utf-8"))
        except Exception:
            continue
        label = job.get("label", "")
        in_launchd = "launchd=SÍ" if label in loaded else "launchd=NO"
        tag = "[DRY-RUN]" if job.get("dry_run") else "[REAL]"
        print(
            f"  • {job['job_id']} | {job['scheduled_for']} | {job['nicho']} {tag} | "
            f"status={job.get('status')} | {in_launchd}"
        )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Programador nativo macOS launchd para Los Crafters SRL (campañas B2B + monitor CRM)"
    )
    parser.add_argument("--schedule-campaign", action="store_true", help="Programa una campaña one-shot en launchd")
    parser.add_argument("--datetime", help="Fecha y hora local exacta: 'YYYY-MM-DD HH:MM'")
    parser.add_argument("--nicho", choices=list(crafters_mailer.TEMPLATES.keys()), help="Plantilla de nicho")
    parser.add_argument("--csv", help="Ruta al CSV de prospectos")
    parser.add_argument("--name", help="Slug corto opcional para identificar el job")
    parser.add_argument("--dry-run", action="store_true", help="Modo prueba segura: ejecuta --preview en vez de --send")

    parser.add_argument("--run-job", help="Ejecuta internamente un job_id programado (usado por launchd)")
    parser.add_argument("--install-crm-monitor", action="store_true", help="Instala el monitor CRM 08:00-23:30 en launchd")
    parser.add_argument("--uninstall-crm-monitor", action="store_true", help="Desinstala el monitor CRM de launchd")
    parser.add_argument("--run-crm", action="store_true", help="Ejecuta un ciclo de monitoreo CRM (usado por launchd)")
    parser.add_argument("--list", action="store_true", help="Lista el estado del monitor CRM y campañas en launchd")
    parser.add_argument("--cancel", help="Cancela y elimina un job_id de campaña programado")

    args = parser.parse_args()

    if args.schedule_campaign:
        if not args.datetime or not args.nicho or not args.csv:
            print("❌ --schedule-campaign requiere --datetime, --nicho y --csv.")
            return 1
        return cmd_schedule_campaign(args)
    if args.run_job:
        return cmd_run_job(args)
    if args.install_crm_monitor:
        return cmd_install_crm_monitor(args)
    if args.uninstall_crm_monitor:
        return cmd_uninstall_crm_monitor(args)
    if args.run_crm:
        return cmd_run_crm(args)
    if args.cancel:
        return cmd_cancel(args)
    if args.list:
        return cmd_list(args)

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
