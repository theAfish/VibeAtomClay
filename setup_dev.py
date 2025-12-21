import os
import subprocess
import sys
import platform
import shutil

def run_command(command, cwd=None, shell=False, env=None, timeout=None, exit_on_error=True):
    """Runs a command and prints output."""
    print(f"Running: {' '.join(command) if isinstance(command, list) else command}")
    try:
        subprocess.run(command, cwd=cwd, shell=shell, env=env, check=True, timeout=timeout)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error running command: {e}")
        if exit_on_error:
            sys.exit(1)
        return False
    except subprocess.TimeoutExpired as e:
        print(f"Error: Command timed out after {timeout} seconds.")
        if exit_on_error:
            sys.exit(1)
        return False

def get_venv_python(venv_path):
    """Returns the path to the python executable in the venv."""
    if platform.system() == "Windows":
        return os.path.join(venv_path, "Scripts", "python.exe")
    else:
        return os.path.join(venv_path, "bin", "python")

def get_venv_pip(venv_path):
    """Returns the path to the pip executable in the venv."""
    if platform.system() == "Windows":
        return os.path.join(venv_path, "Scripts", "pip.exe")
    else:
        return os.path.join(venv_path, "bin", "pip")

def create_venv(venv_path):
    """Creates a virtual environment if it doesn't exist."""
    if not os.path.exists(venv_path):
        print(f"Creating virtual environment at {venv_path}...")
        subprocess.check_call([sys.executable, "-m", "venv", venv_path])
    else:
        print(f"Virtual environment already exists at {venv_path}")

def setup_submodules(root_dir):
    """Initializes and updates git submodules."""
    print("\n--- Setting up Git Submodules ---")
    if os.path.exists(os.path.join(root_dir, ".git")):
        # Timeout set to 600 seconds (10 minutes) to prevent indefinite hanging
        # Removed --depth 1 as it can cause 'not our ref' errors if the commit isn't the tip
        cmd = ["git", "submodule", "update", "--init", "--recursive", "--jobs", "4"]
        
        def cleanup_submodules():
            print("Cleaning up broken submodules...")
            run_command(["git", "submodule", "deinit", "-f", "--all"], cwd=root_dir, exit_on_error=False)

        # Try first attempt
        if not run_command(cmd, cwd=root_dir, timeout=600, exit_on_error=False):
            print("\n!!! Submodule update failed. Attempting to clean and retry... !!!")
            
            cleanup_submodules()
            
            # Retry update
            print("Retrying submodule update with --remote (fetching latest)...")
            retry_cmd = ["git", "submodule", "update", "--init", "--recursive", "--remote", "--jobs", "4"]
            if not run_command(retry_cmd, cwd=root_dir, timeout=600, exit_on_error=False):
                print("\n!!! Retry failed. Cleaning up to avoid 'staged changes' mess... !!!")
                cleanup_submodules()
                print("Setup failed due to network issues. Please check your connection and try again.")
                sys.exit(1)
            
    else:
        print("Not a git repository or .git missing. Skipping submodule setup.")

def setup_frontend(root_dir):
    """Installs frontend dependencies."""
    print("\n--- Setting up Frontend ---")
    frontend_dir = os.path.join(root_dir, "packages", "frontend")
    
    if not os.path.exists(frontend_dir):
        print(f"Frontend directory not found at {frontend_dir}")
        return

    if not os.path.exists(os.path.join(frontend_dir, "package.json")):
        print(f"package.json not found in {frontend_dir}. Did submodules update correctly?")
        return

    # Check for npm
    npm_cmd = "npm.cmd" if platform.system() == "Windows" else "npm"
    try:
        subprocess.check_call([npm_cmd, "--version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("Error: 'npm' is not installed or not in PATH. Please install Node.js.")
        sys.exit(1)

    print("Installing frontend dependencies...")
    run_command([npm_cmd, "install"], cwd=frontend_dir, shell=False)

def setup_python_env(env_name, requirements_path, root_dir):
    """Sets up a python environment and installs requirements."""
    print(f"\n--- Setting up {env_name} ---")
    
    envs_dir = os.path.join(root_dir, "envs")
    if not os.path.exists(envs_dir):
        os.makedirs(envs_dir)
        
    venv_path = os.path.join(envs_dir, env_name)
    create_venv(venv_path)
    
    pip_exe = get_venv_pip(venv_path)
    python_exe = get_venv_python(venv_path)
    
    # Upgrade pip
    run_command([python_exe, "-m", "pip", "install", "--upgrade", "pip"])
    
    if os.path.exists(requirements_path):
        print(f"Installing requirements from {requirements_path}...")
        run_command([pip_exe, "install", "-r", requirements_path])
    else:
        print(f"Warning: requirements.txt not found at {requirements_path}")

def copy_server_env(root_dir):
    """Copies the .env file from config to agent-server."""
    print("\n--- Setting up Server Environment Variables ---")
    source = os.path.join(root_dir, "config", ".env")
    dest_dir = os.path.join(root_dir, "packages", "agent-server", "agentom")
    dest = os.path.join(dest_dir, ".env")

    if os.path.exists(source):
        if not os.path.exists(dest_dir):
             print(f"Destination directory {dest_dir} does not exist. Creating it...")
             os.makedirs(dest_dir, exist_ok=True)
        
        print(f"Copying {source} to {dest}...")
        shutil.copy2(source, dest)
    else:
        print(f"Warning: Source .env file not found at {source}")

def main():
    root_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 1. Git Submodules
    setup_submodules(root_dir)
    
    # 2. Frontend
    setup_frontend(root_dir)
    
    # 3. Middleware Environment
    middleware_reqs = os.path.join(root_dir, "packages", "middleware", "requirements.txt")
    setup_python_env("middleware-env", middleware_reqs, root_dir)
    
    # 4. Server Environment
    server_reqs = os.path.join(root_dir, "packages", "agent-server", "requirements.txt")
    setup_python_env("server-env", server_reqs, root_dir)

    # 5. Copy Server .env
    copy_server_env(root_dir)

    print("\n\nSetup complete! You can now run 'python start_dev.py' to start the services.")

if __name__ == "__main__":
    main()
