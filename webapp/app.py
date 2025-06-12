from flask import Flask, render_template, request, redirect, url_for, flash
import subprocess
import threading
import os
import json
import signal
import time

app = Flask(__name__)
app.secret_key = 'crawler_secret_key'  # Needed for flash messages
crawler_process = None  # Global to store process handle
crawler_thread = None  # Global to track the thread

# Get absolute path to the webcrawler directory
SCRAPY_PROJECT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'webcrawler'))
DATA_FILE = os.path.join(SCRAPY_PROJECT_DIR, "crawled_data.json")


@app.route("/", methods=["GET", "POST"])
def index():
    global crawler_process, crawler_thread

    if request.method == "POST":
        if "start" in request.form:
            start_url = request.form.get("start_url")
            if start_url:
                if crawler_process is None:
                    # Clear previous results
                    if os.path.exists(DATA_FILE):
                        try:
                            os.remove(DATA_FILE)
                        except Exception as e:
                            print(f"Error removing data file: {e}")

                    def run_spider():
                        global crawler_process
                        try:
                            # Ensure the directory structure exists
                            os.makedirs(os.path.join(SCRAPY_PROJECT_DIR, "webcrawler", "spiders"), exist_ok=True)

                            # Setup Scrapy command
                            cmd = [
                                "scrapy", "crawl", "crawler_spider",
                                "-a", f"start_url={start_url}"
                            ]

                            # Print command for debugging
                            print(f"Running command: {' '.join(cmd)} in {SCRAPY_PROJECT_DIR}")
                            print(f"Current directory: {os.getcwd()}")
                            print(f"Data file will be saved to: {DATA_FILE}")

                            # Setup a signal handler for the subprocess
                            crawler_process = subprocess.Popen(
                                cmd,
                                cwd=SCRAPY_PROJECT_DIR,  # Use absolute path
                                stderr=subprocess.PIPE,
                                stdout=subprocess.PIPE,
                                text=True,  # Return strings instead of bytes
                                # Setup process group for better signal handling
                                preexec_fn=os.setsid if os.name != 'nt' else None
                            )

                            stdout, stderr = crawler_process.communicate()

                            # For debugging
                            if crawler_process.returncode != 0:
                                print(f"Crawler exited with code: {crawler_process.returncode}")
                                print(f"STDOUT: {stdout}")
                                print(f"STDERR: {stderr}")
                            else:
                                print("Crawler finished successfully")

                            # Make sure data is refreshed in the UI
                            if os.path.exists(DATA_FILE) and os.path.getsize(DATA_FILE) > 0:
                                try:
                                    with open(DATA_FILE, "r", encoding="utf-8") as f:
                                        data = json.load(f)
                                        print(f"Final data file contents: {len(data)} records")
                                except Exception as e:
                                    print(f"Error reading data file: {e}")
                            else:
                                print(f"Data file not found or empty: {DATA_FILE}")

                            crawler_process = None
                        except Exception as e:
                            print(f"Error running crawler: {e}")
                            import traceback
                            traceback.print_exc()
                            crawler_process = None

                    crawler_thread = threading.Thread(target=run_spider)
                    crawler_thread.daemon = True  # Make thread exit when main thread exits
                    crawler_thread.start()

                    flash("Crawler started!", "success")
                else:
                    flash("Crawler is already running", "warning")
            else:
                flash("Please enter a start URL", "danger")

        elif "stop" in request.form:
            if crawler_process:
                try:
                    print(f"Attempting to stop crawler process {crawler_process.pid}")

                    # Try graceful termination first
                    if os.name == 'nt':  # Windows
                        crawler_process.terminate()
                    else:  # Unix/Linux
                        os.kill(crawler_process.pid, signal.SIGTERM)

                    print(f"Sent termination signal to crawler process {crawler_process.pid}")

                    # Wait a bit for process to finish and ensure data is written
                    max_wait = 5  # seconds
                    for i in range(max_wait):
                        if crawler_process.poll() is not None:  # Process has terminated
                            print(f"Process terminated after {i + 1}s")
                            break
                        time.sleep(1)

                    # Force kill if still running after waiting
                    if crawler_process.poll() is None:
                        print(f"Process still running after {max_wait}s, sending kill signal")
                        if os.name == 'nt':  # Windows
                            subprocess.run(['taskkill', '/F', '/T', '/PID', str(crawler_process.pid)])
                        else:  # Unix/Linux
                            os.kill(crawler_process.pid, signal.SIGKILL)

                    # Wait for file to be fully written
                    time.sleep(1)

                    crawler_process = None
                    flash("Crawler stopped and data saved", "info")
                except Exception as e:
                    print(f"Error stopping crawler: {e}")
                    import traceback
                    traceback.print_exc()
                    flash(f"Error stopping crawler: {e}", "danger")
            else:
                flash("No crawler is running", "warning")

            return redirect(url_for("index"))

    # Load results
    data = []
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            print(f"Loaded {len(data)} records from {DATA_FILE}")
        except Exception as e:
            print(f"Error loading data: {e}")
            flash(f"Error loading crawler data: {e}", "danger")

    # Check if crawler is still running
    is_running = crawler_process is not None and crawler_thread and crawler_thread.is_alive()

    return render_template("index.html", data=data, is_running=is_running)


@app.route("/clear", methods=["POST"])
def clear_data():
    if os.path.exists(DATA_FILE):
        os.remove(DATA_FILE)
        flash("Crawler data cleared", "success")
    return redirect(url_for("index"))


if __name__ == "__main__":
    app.run(debug=True)