"""
Views for the GenePattern Module Generator Web UI.
"""

import os
import json
import subprocess
import threading
from pathlib import Path
from datetime import datetime
from functools import wraps

from django.shortcuts import render, redirect
from django.http import JsonResponse, FileResponse, Http404
from django.conf import settings
from django.contrib import messages

# Track currently running modules per user
running_modules = {}  # {username: {module_name: True}}


def login_required(view_func):
    """Decorator to require login for views."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.session.get('username'):
            return redirect('login')
        return view_func(request, *args, **kwargs)
    return wrapper


def get_user_stats_path(username):
    """Get path to user stats JSON file."""
    user_dir = settings.GENERATED_MODULES_DIR / username
    return user_dir / 'user_stats.json'


def load_user_stats(username):
    """Load user statistics from JSON file."""
    stats_path = get_user_stats_path(username)
    if stats_path.exists():
        try:
            with open(stats_path, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {'run_count': 0, 'runs': []}


def save_user_stats(username, stats):
    """Save user statistics to JSON file."""
    stats_path = get_user_stats_path(username)
    stats_path.parent.mkdir(parents=True, exist_ok=True)
    with open(stats_path, 'w') as f:
        json.dump(stats, f, indent=2)


def get_max_runs_for_user(username):
    """Get max runs for a user (check user-specific override first)."""
    stats = load_user_stats(username)
    return stats.get('max_runs', settings.MAX_RUNS_PER_USER)


def get_user_modules(username):
    """Get list of generated modules for a user."""
    user_dir = settings.GENERATED_MODULES_DIR / username
    modules = []
    
    # Add currently running modules first
    if username in running_modules:
        for module_name in running_modules[username]:
            module_path = user_dir / module_name
            modules.append({
                'name': module_name,
                'status': 'running',
                'path': str(module_path),
            })

    if user_dir.exists():
        for item in sorted(user_dir.iterdir(), reverse=True):
            if item.is_dir() and not item.name.startswith('.'):
                # Skip if already added as running
                if username in running_modules and item.name in running_modules[username]:
                    continue

                # Check for status.json to determine completion status
                status_file = item / 'status.json'
                status = 'unknown'
                if status_file.exists():
                    try:
                        with open(status_file, 'r') as f:
                            status_data = json.load(f)
                            # Check if all artifacts are validated
                            artifacts = status_data.get('artifacts_status', {})
                            if artifacts:
                                all_valid = all(
                                    a.get('validated', False) 
                                    for a in artifacts.values()
                                )
                                status = 'success' if all_valid else 'error'
                            elif status_data.get('error_messages'):
                                status = 'error'
                            else:
                                status = 'in_progress'
                    except (json.JSONDecodeError, IOError):
                        status = 'error'
                
                modules.append({
                    'name': item.name,
                    'status': status,
                    'path': str(item),
                })
    
    return modules


def login_view(request):
    """Handle user login."""
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        
        if username in settings.AUTH_USERS and settings.AUTH_USERS[username] == password:
            request.session['username'] = username
            return redirect('dashboard')
        else:
            messages.error(request, 'Invalid username or password')
    
    return render(request, 'generator/login.html')


def logout_view(request):
    """Handle user logout."""
    request.session.flush()
    return redirect('login')


@login_required
def dashboard(request):
    """Main dashboard view with form and module list."""
    username = request.session.get('username')
    modules = get_user_modules(username)
    stats = load_user_stats(username)
    max_runs = get_max_runs_for_user(username)
    
    # Get list of resumable modules (those with status.json)
    resumable_modules = []
    for module in modules:
        status_file = Path(module['path']) / 'status.json'
        if status_file.exists():
            resumable_modules.append(module['name'])
    
    context = {
        'username': username,
        'modules': modules,
        'run_count': stats.get('run_count', 0),
        'max_runs': max_runs,
        'resumable_modules': resumable_modules,
    }
    
    return render(request, 'generator/dashboard.html', context)


def run_generate_script(username, form_data, module_toolkit_path, output_dir, module_name):
    """Run the generate-module.py script in a background thread."""
    global running_modules

    # For resume, use the existing module name; for new runs, we'll detect the created directory
    actual_module_name = form_data.get('resume') or module_name

    # Mark module as running
    if username not in running_modules:
        running_modules[username] = {}
    running_modules[username][actual_module_name] = True

    # Create the log file in the user's output directory (not the module directory yet)
    # For new runs, we'll move it once we know the actual module directory
    temp_log_file = output_dir / f'.{actual_module_name}_console.log'

    # Build command
    cmd = ['python', '-u', 'generate-module.py']  # -u for unbuffered output

    # Add required arguments
    if form_data.get('name'):
        cmd.extend(['--name', form_data['name']])
    cmd.extend(['--output-dir', str(output_dir)])
    
    # Add optional arguments
    if form_data.get('version'):
        cmd.extend(['--version', form_data['version']])
    if form_data.get('language'):
        cmd.extend(['--language', form_data['language']])
    if form_data.get('description'):
        cmd.extend(['--description', form_data['description']])
    if form_data.get('repository_url'):
        cmd.extend(['--repository-url', form_data['repository_url']])
    if form_data.get('documentation_url'):
        cmd.extend(['--documentation-url', form_data['documentation_url']])
    if form_data.get('instructions'):
        cmd.extend(['--instructions', form_data['instructions']])
    
    # Dev mode
    if form_data.get('dev_mode') == 'on':
        cmd.append('--dev-mode')
    
    # Resume
    if form_data.get('resume'):
        resume_path = output_dir / form_data['resume']
        cmd.extend(['--resume', str(resume_path)])

    actual_module_dir = None

    # Run the script and capture output
    try:
        with open(temp_log_file, 'w') as log:
            log.write(f"=== Module Generation Started: {datetime.now().isoformat()} ===\n")
            log.write(f"Command: {' '.join(cmd)}\n")
            log.write("=" * 60 + "\n\n")
            log.flush()

            process = subprocess.Popen(
                cmd,
                cwd=str(module_toolkit_path),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1  # Line buffered
            )

            # Stream output to log file and detect actual module directory
            for line in process.stdout:
                log.write(line)
                log.flush()

                # Detect the actual module directory from output
                if 'Creating module directory:' in line and actual_module_dir is None:
                    # Extract the directory path from the line
                    # Format: [timestamp] INFO: Creating module directory: /path/to/module_dir
                    try:
                        dir_path = line.split('Creating module directory:')[1].strip()
                        actual_module_dir = Path(dir_path).name

                        # Update running_modules with actual name if different
                        if actual_module_dir != actual_module_name:
                            running_modules[username][actual_module_dir] = True
                            if actual_module_name in running_modules[username]:
                                del running_modules[username][actual_module_name]
                            actual_module_name = actual_module_dir
                    except (IndexError, ValueError):
                        pass

            process.wait()

            log.write(f"\n{'=' * 60}\n")
            log.write(f"=== Process exited with code: {process.returncode} ===\n")
            log.write(f"=== Completed: {datetime.now().isoformat()} ===\n")

    except subprocess.TimeoutExpired:
        with open(temp_log_file, 'a') as log:
            log.write("\n\n=== ERROR: Process timed out after 30 minutes ===\n")
    except Exception as e:
        with open(temp_log_file, 'a') as log:
            log.write(f"\n\n=== ERROR: {str(e)} ===\n")
    finally:
        # Move log file to the actual module directory if it exists
        if actual_module_dir:
            final_log_path = output_dir / actual_module_dir / 'console.log'
            try:
                if final_log_path.parent.exists():
                    import shutil
                    shutil.move(str(temp_log_file), str(final_log_path))
            except Exception:
                pass

        # Clean up temp log file if it still exists
        try:
            if temp_log_file.exists():
                temp_log_file.unlink()
        except Exception:
            pass

        # Remove from running modules
        if username in running_modules:
            if actual_module_name in running_modules[username]:
                del running_modules[username][actual_module_name]
            if module_name in running_modules[username]:
                del running_modules[username][module_name]
            if not running_modules[username]:
                del running_modules[username]


@login_required
def generate_module(request):
    """Handle module generation request."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    
    username = request.session.get('username')
    stats = load_user_stats(username)
    max_runs = get_max_runs_for_user(username)
    
    # Check run limit
    if stats.get('run_count', 0) >= max_runs:
        return JsonResponse({
            'error': f'You have reached your maximum of {max_runs} runs. Contact an administrator to increase your limit.'
        }, status=403)
    
    # Get form data
    form_data = {
        'name': request.POST.get('name', '').strip(),
        'version': request.POST.get('version', '').strip(),
        'language': request.POST.get('language', '').strip(),
        'description': request.POST.get('description', '').strip(),
        'repository_url': request.POST.get('repository_url', '').strip(),
        'documentation_url': request.POST.get('documentation_url', '').strip(),
        'instructions': request.POST.get('instructions', '').strip(),
        'dev_mode': request.POST.get('dev_mode', ''),
        'resume': request.POST.get('resume', '').strip(),
    }
    
    # Validate required fields
    if not form_data['name'] and not form_data['resume']:
        return JsonResponse({'error': 'Tool name is required'}, status=400)
    
    # Update stats
    stats['run_count'] = stats.get('run_count', 0) + 1
    stats.setdefault('runs', []).append({
        'timestamp': datetime.now().isoformat(),
        'name': form_data['name'] or form_data['resume'],
        'resume': bool(form_data['resume']),
    })
    save_user_stats(username, stats)
    
    # Set output directory to user's folder
    output_dir = settings.GENERATED_MODULES_DIR / username
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate expected module directory name for tracking
    if form_data['resume']:
        expected_module = form_data['resume']
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        tool_name_clean = form_data['name'].lower().replace(' ', '_').replace('-', '_')
        expected_module = f"{tool_name_clean}_{timestamp}"
    
    # Run script in background thread
    thread = threading.Thread(
        target=run_generate_script,
        args=(username, form_data, settings.MODULE_TOOLKIT_PATH, output_dir, expected_module)
    )
    thread.start()
    
    return JsonResponse({
        'success': True,
        'message': 'Module generation started',
        'module': expected_module,
    })


@login_required
def module_status(request, module_dir):
    """Get status of a module generation."""
    username = request.session.get('username')
    module_path = settings.GENERATED_MODULES_DIR / username / module_dir
    
    # Check if module is currently running
    is_running = username in running_modules and module_dir in running_modules.get(username, {})

    if not module_path.exists():
        if is_running:
            return JsonResponse({'status': 'running', 'running': True})
        return JsonResponse({'status': 'not_found'})
    
    # Check console.log for completion marker to detect if script has finished
    log_file = module_path / 'console.log'
    script_completed = False
    if log_file.exists():
        try:
            with open(log_file, 'r') as f:
                log_content = f.read()
                # Check for completion markers in the log
                if '=== Process exited with code:' in log_content or '=== Completed:' in log_content:
                    script_completed = True
                    # If script completed, make sure it's not marked as running
                    is_running = False
        except IOError:
            pass

    status_file = module_path / 'status.json'

    # If still running (and script hasn't completed), return running status
    if is_running and not script_completed:
        return JsonResponse({'status': 'running', 'running': True})

    if not status_file.exists():
        # If script completed but no status.json, it's an error
        if script_completed:
            return JsonResponse({'status': 'error', 'running': False})
        return JsonResponse({'status': 'in_progress', 'running': False})

    try:
        with open(status_file, 'r') as f:
            status_data = json.load(f)
        
        # Determine overall status
        # First check for error_messages - this catches early failures
        if status_data.get('error_messages') and len(status_data.get('error_messages', [])) > 0:
            status = 'error'
        else:
            # Check artifacts status
            artifacts = status_data.get('artifacts_status', {})
            if artifacts:
                all_valid = all(a.get('validated', False) for a in artifacts.values())
                status = 'success' if all_valid else 'error'
            elif not status_data.get('research_complete', False) or not status_data.get('planning_complete', False):
                # Research or planning not complete means failure
                status = 'error' if script_completed else 'in_progress'
            else:
                status = 'in_progress'

        return JsonResponse({
            'status': status,
            'running': False,
            'data': status_data,
        })
    except (json.JSONDecodeError, IOError):
        return JsonResponse({'status': 'error', 'running': False})


@login_required
def console_log(request, module_dir):
    """Get console log output for a module, with offset support for incremental updates."""
    username = request.session.get('username')
    user_dir = settings.GENERATED_MODULES_DIR / username
    module_path = user_dir / module_dir
    log_file = module_path / 'console.log'

    # Check for temp log files - could be named after predicted or actual module name
    # The temp log file might be named after the original predicted name or the actual name
    temp_log_file = user_dir / f'.{module_dir}_console.log'

    # Also search for any temp log file that might match this module
    # This handles the case where the module name changed after creation
    possible_temp_files = list(user_dir.glob('.*_console.log'))

    # Get offset from query parameter
    offset = int(request.GET.get('offset', 0))

    # Determine which log file to read
    active_log_file = None

    # First, check the exact temp log file name
    if temp_log_file.exists():
        active_log_file = temp_log_file
    else:
        # Search for a temp log file that might be for a running module
        # Check if any temp log matches a module that's currently running
        for temp_file in possible_temp_files:
            # Extract the module name from the temp file name
            # Format: .{module_name}_console.log
            temp_name = temp_file.name[1:-12]  # Remove leading '.' and trailing '_console.log'

            # Check if this is for a currently running module
            if username in running_modules:
                # If the requested module_dir is in running modules, or if the temp file's module is
                if module_dir in running_modules[username] or temp_name in running_modules[username]:
                    # Check if this temp file corresponds to a module with a similar prefix
                    # (handles timestamp differences)
                    module_prefix = module_dir.rsplit('_', 2)[0] if '_' in module_dir else module_dir
                    temp_prefix = temp_name.rsplit('_', 2)[0] if '_' in temp_name else temp_name
                    if module_prefix == temp_prefix:
                        active_log_file = temp_file
                        break

    # Fall back to the final log file in the module directory
    if not active_log_file and log_file.exists():
        active_log_file = log_file

    if not active_log_file:
        return JsonResponse({
            'content': '',
            'offset': 0,
            'total_size': 0,
        })

    try:
        file_size = active_log_file.stat().st_size

        with open(active_log_file, 'r') as f:
            if offset > 0:
                f.seek(offset)
            content = f.read()

        return JsonResponse({
            'content': content,
            'offset': file_size,
            'total_size': file_size,
        })
    except IOError:
        return JsonResponse({
            'content': '',
            'offset': offset,
            'total_size': 0,
        })


@login_required
def module_files(request, module_dir):
    """Get list of files in a module directory."""
    username = request.session.get('username')
    module_path = settings.GENERATED_MODULES_DIR / username / module_dir
    
    if not module_path.exists():
        raise Http404("Module not found")
    
    files = []
    for item in sorted(module_path.iterdir()):
        if item.is_file():
            files.append({
                'name': item.name,
                'size': item.stat().st_size,
            })
    
    return JsonResponse({'files': files, 'module': module_dir})


@login_required
def download_file(request, module_dir, filename):
    """Download a file from a module directory."""
    username = request.session.get('username')
    file_path = settings.GENERATED_MODULES_DIR / username / module_dir / filename
    
    if not file_path.exists() or not file_path.is_file():
        raise Http404("File not found")
    
    # Security check - ensure path is within user's directory
    try:
        file_path.resolve().relative_to((settings.GENERATED_MODULES_DIR / username).resolve())
    except ValueError:
        raise Http404("File not found")
    
    return FileResponse(open(file_path, 'rb'), as_attachment=True, filename=filename)
