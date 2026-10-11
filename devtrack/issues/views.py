import json
import os
import tempfile
import threading
from pathlib import Path
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from .models import Reporter, Issue, CriticalIssue, LowPriorityIssue

ISSUES_FILE = Path(settings.BASE_DIR) / 'issues.json'
REPORTERS_FILE = Path(settings.BASE_DIR) / 'reporters.json'

_file_locks = {}
_locks_guard = threading.RLock()


def get_lock(filepath):
    path_key = str(Path(filepath).resolve())
    with _locks_guard:
        if path_key not in _file_locks:
            _file_locks[path_key] = threading.RLock()
        return _file_locks[path_key]


def ensure_file_initialized(filepath):
    path_obj = Path(filepath).resolve()
    lock = get_lock(path_obj)
    with lock:
        if not path_obj.exists():
            write_json_atomic(path_obj, [])


def init_storage_files():
    ensure_file_initialized(REPORTERS_FILE)
    ensure_file_initialized(ISSUES_FILE)


def read_json(filepath):
    path_obj = Path(filepath).resolve()
    lock = get_lock(path_obj)
    with lock:
        if not path_obj.exists():
            write_json_atomic(path_obj, [])
            return []
        try:
            with open(path_obj, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if not content:
                    write_json_atomic(path_obj, [])
                    return []
                return json.loads(content)
        except (json.JSONDecodeError, OSError):
            write_json_atomic(path_obj, [])
            return []


def write_json_atomic(filepath, data):
    path_obj = Path(filepath).resolve()
    dir_name = path_obj.parent
    dir_name.mkdir(parents=True, exist_ok=True)
    lock = get_lock(path_obj)

    with lock:
        temp_file = tempfile.NamedTemporaryFile(
            mode='w',
            dir=dir_name,
            delete=False,
            encoding='utf-8',
            suffix='.tmp'
        )
        temp_path = temp_file.name
        try:
            json.dump(data, temp_file, indent=2)
            temp_file.flush()
            os.fsync(temp_file.fileno())
            temp_file.close()
            os.replace(temp_path, str(path_obj))
        except Exception:
            temp_file.close()
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    pass
            raise


@csrf_exempt
def reporters_view(request):
    if request.method == 'GET':
        reporters = read_json(REPORTERS_FILE)
        if 'id' in request.GET:
            query_id = request.GET.get('id')
            reporter = next((r for r in reporters if str(r.get('id')) == str(query_id)), None)
            if reporter is not None:
                return JsonResponse(reporter, status=200)
            return JsonResponse({'error': 'Reporter not found'}, status=404)
        return JsonResponse(reporters, safe=False, status=200)

    elif request.method == 'POST':
        try:
            data = json.loads(request.body.decode('utf-8'))
        except (json.JSONDecodeError, UnicodeDecodeError, ValueError):
            return JsonResponse({'error': 'Malformed JSON'}, status=400)

        if not isinstance(data, dict):
            return JsonResponse({'error': 'Invalid payload, expected a JSON object'}, status=400)

        if 'id' not in data or data.get('id') is None or data.get('id') == '':
            return JsonResponse({'error': 'id is required'}, status=400)

        reporter = Reporter(
            id=data.get('id'),
            name=data.get('name'),
            email=data.get('email'),
            team=data.get('team')
        )

        try:
            reporter.validate()
        except ValueError as e:
            return JsonResponse({'error': str(e)}, status=400)

        with get_lock(REPORTERS_FILE):
            reporters = read_json(REPORTERS_FILE)
            if any(str(r.get('id')) == str(reporter.id) for r in reporters):
                return JsonResponse({'error': f'Reporter with id {reporter.id} already exists'}, status=400)

            reporter_dict = reporter.to_dict()
            reporters.append(reporter_dict)
            write_json_atomic(REPORTERS_FILE, reporters)
            return JsonResponse(reporter_dict, status=201)

    return JsonResponse({'error': 'Method not allowed'}, status=405)


@csrf_exempt
def issues_view(request):
    if request.method == 'GET':
        issues = read_json(ISSUES_FILE)
        if 'id' in request.GET:
            query_id = request.GET.get('id')
            issue = next((iss for iss in issues if str(iss.get('id')) == str(query_id)), None)
            if issue is not None:
                return JsonResponse(issue, status=200)
            return JsonResponse({'error': 'Issue not found'}, status=404)
        elif 'status' in request.GET:
            status_param = request.GET.get('status')
            filtered = [iss for iss in issues if iss.get('status') == status_param]
            return JsonResponse(filtered, safe=False, status=200)
        return JsonResponse(issues, safe=False, status=200)

    elif request.method == 'POST':
        try:
            data = json.loads(request.body.decode('utf-8'))
        except (json.JSONDecodeError, UnicodeDecodeError, ValueError):
            return JsonResponse({'error': 'Malformed JSON'}, status=400)

        if not isinstance(data, dict):
            return JsonResponse({'error': 'Invalid payload, expected a JSON object'}, status=400)

        if 'id' not in data or data.get('id') is None or data.get('id') == '':
            return JsonResponse({'error': 'id is required'}, status=400)

        with get_lock(ISSUES_FILE):
            reporters = read_json(REPORTERS_FILE)
            reporter_id = data.get('reporter_id')
            if reporter_id is None or not any(str(r.get('id')) == str(reporter_id) for r in reporters):
                return JsonResponse({'error': 'Reporter does not exist'}, status=400)

            issues = read_json(ISSUES_FILE)
            if any(str(iss.get('id')) == str(data.get('id')) for iss in issues):
                return JsonResponse({'error': f'Issue with id {data.get("id")} already exists'}, status=400)

            priority = data.get('priority')
            issue_kwargs = {
                'id': data.get('id'),
                'title': data.get('title'),
                'description': data.get('description'),
                'status': data.get('status'),
                'priority': priority,
                'reporter_id': reporter_id,
                'created_at': data.get('created_at'),
            }

            if priority == 'critical':
                issue = CriticalIssue(**issue_kwargs)
            elif priority == 'low':
                issue = LowPriorityIssue(**issue_kwargs)
            else:
                issue = Issue(**issue_kwargs)

            try:
                issue.validate()
            except ValueError as e:
                return JsonResponse({'error': str(e)}, status=400)

            response_data = issue.to_dict()
            response_data['message'] = issue.describe()
            issues.append(response_data)
            write_json_atomic(ISSUES_FILE, issues)
            return JsonResponse(response_data, status=201)

    return JsonResponse({'error': 'Method not allowed'}, status=405)
