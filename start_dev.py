import subprocess
import os
import sys
import platform
import time
import signal

def get_venv_bin_dir(venv_path):
    """Returns the binary directory of the virtual environment based on OS."""
    if platform.system() == "Windows":
        return os.path.join(venv_path, "Scripts")
    else:
        return os.path.join(venv_path, "bin")

def get_executable(venv_path, executable_name):
    """Returns the path to an executable inside the venv."""
    bin_dir = get_venv_bin_dir(venv_path)
    if platform.system() == "Windows":
        # Try with .exe first, then without
        exe_path = os.path.join(bin_dir, f"{executable_name}.exe")
        if os.path.exists(exe_path):
            return exe_path
        return os.path.join(bin_dir, executable_name)
    else:
        return os.path.join(bin_dir, executable_name)

def main():
    root_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Define paths
    middleware_env = os.path.join(root_dir, "envs", "middleware-env")
    server_env = os.path.join(root_dir, "envs", "server-env")
    
    middleware_dir = os.path.join(root_dir, "packages", "middleware")
    server_dir = os.path.join(root_dir, "packages", "agent-server")
    frontend_dir = os.path.join(root_dir, "packages", "frontend")

    processes = []

    print(f"Detected OS: {platform.system()}")
    print("Starting development services...")

    try:
        # 1. Middleware
        # Command: python main.py
        print("[Middleware] Starting...")
        mw_python = get_executable(middleware_env, "python")
        mw_process = subprocess.Popen(
            [mw_python, "main.py"],
            cwd=middleware_dir,
            shell=False
        )
        processes.append(("Middleware", mw_process))

        # 2. Server
        # Command: adk api_server agentom
        print("[Server] Starting...")
        adk_exe = get_executable(server_env, "adk")
        server_process = subprocess.Popen(
            [adk_exe, "api_server", "agentom"],
            cwd=server_dir,
            shell=False
        )
        processes.append(("Server", server_process))

        # 3. Frontend
        # Command: npm run dev
        print("[Frontend] Starting...")
        npm_cmd = "npm.cmd" if platform.system() == "Windows" else "npm"
        frontend_process = subprocess.Popen(
            [npm_cmd, "run", "dev"],
            cwd=frontend_dir,
            shell=False
        )
        processes.append(("Frontend", frontend_process))

        print("\nAll services are running. Press Ctrl+C to stop them.\n")
        
        # Monitor processes
        while True:
            time.sleep(1)
            for name, p in processes:
                if p.poll() is not None:
                    print(f"\nProcess '{name}' exited unexpectedly with code {p.returncode}")
                    raise KeyboardInterrupt

    except KeyboardInterrupt:
        print("\n\nStopping all services...")
        
        # On Windows, Ctrl+C is sent to all processes attached to the console.
        # The subprocesses should receive the signal and start their own cleanup.
        # We wait for them to exit gracefully.
        print("Waiting for services to shut down gracefully...")
        start_wait = time.time()
        grace_period = 5  # seconds
        
        while time.time() - start_wait < grace_period:
            if all(p.poll() is not None for _, p in processes):
                break
            time.sleep(0.1)

        # Force kill if still running after grace period
        for name, p in processes:
            if p.poll() is None:
                print(f"Terminating {name} (timed out)...")
                p.terminate()
        
        # Final wait to ensure handles are released
        time.sleep(0.5)
        for name, p in processes:
            if p.poll() is None:
                print(f"Force killing {name}...")
                p.kill()
                
        print("Shutdown complete.")

if __name__ == "__main__":
    main()
