import json
import os
import subprocess
import sys
import threading
import uuid

from job_store import create_job, update_job, get_job

RESULTS_DIR = "load_test_results"
os.makedirs(RESULTS_DIR, exist_ok=True)


def _run_api_job(job_id, target_url, target_path, cases, users, spawn_rate, duration_seconds):
    job_dir = os.path.join(RESULTS_DIR, job_id)
    os.makedirs(job_dir, exist_ok=True)

    cases_file = os.path.join(job_dir, "cases.json")
    with open(cases_file, "w") as f:
        json.dump(cases, f)

    csv_prefix = os.path.join(job_dir, "result")

    env = os.environ.copy()
    env["LOCUST_CASES_FILE"] = cases_file
    env["LOCUST_TARGET_PATH"] = target_path

    locustfile_path = os.path.join(os.path.dirname(__file__), "locust_tests", "dynamic_locustfile.py")
    _run_locust(job_id, locustfile_path, env, target_url, users, spawn_rate, duration_seconds, csv_prefix)


def _run_website_job(job_id, target_url, paths, users, spawn_rate, duration_seconds):
    job_dir = os.path.join(RESULTS_DIR, job_id)
    os.makedirs(job_dir, exist_ok=True)

    paths_file = os.path.join(job_dir, "paths.json")
    with open(paths_file, "w") as f:
        json.dump(paths, f)

    csv_prefix = os.path.join(job_dir, "result")

    env = os.environ.copy()
    env["LOCUST_PATHS_FILE"] = paths_file

    locustfile_path = os.path.join(os.path.dirname(__file__), "locust_tests", "website_locustfile.py")
    _run_locust(job_id, locustfile_path, env, target_url, users, spawn_rate, duration_seconds, csv_prefix)


def _run_locust(job_id, locustfile_path, env, target_url, users, spawn_rate, duration_seconds, csv_prefix):
    if not os.path.exists(locustfile_path):
        update_job(job_id, status="failed", error=f"locustfile not found at {locustfile_path}")
        return

    cmd = [
        sys.executable, "-m", "locust",
        "-f", locustfile_path,
        "--headless",
        "-u", str(users),
        "-r", str(spawn_rate),
        "-t", f"{duration_seconds}s",
        "--host", target_url,
        "--csv", csv_prefix,
    ]

    update_job(job_id, status="running")

    try:
        proc = subprocess.run(
            cmd, env=env, capture_output=True, text=True,
            timeout=duration_seconds + 60,
        )
        stats_csv = None
        stats_file = f"{csv_prefix}_stats.csv"
        if os.path.exists(stats_file):
            with open(stats_file) as f:
                stats_csv = f.read()

        update_job(
            job_id,
            status="completed",
            stdout=proc.stdout[-3000:],
            stderr=proc.stderr[-3000:],
            stats_csv=stats_csv,
        )
    except subprocess.TimeoutExpired:
        update_job(job_id, status="timeout")
    except Exception as e:
        update_job(job_id, status="failed", error=str(e))


def start_load_test(target_url, target_path, cases, users=5, spawn_rate=1, duration_seconds=30):
    job_id = str(uuid.uuid4())
    create_job(job_id, target_url, users, spawn_rate, duration_seconds)
    thread = threading.Thread(
        target=_run_api_job,
        args=(job_id, target_url, target_path, cases, users, spawn_rate, duration_seconds),
        daemon=True,
    )
    thread.start()
    return job_id


def start_website_load_test(target_url, paths, users=5, spawn_rate=1, duration_seconds=30):
    job_id = str(uuid.uuid4())
    create_job(job_id, target_url, users, spawn_rate, duration_seconds)
    thread = threading.Thread(
        target=_run_website_job,
        args=(job_id, target_url, paths, users, spawn_rate, duration_seconds),
        daemon=True,
    )
    thread.start()
    return job_id


def get_job_status(job_id):
    return get_job(job_id)