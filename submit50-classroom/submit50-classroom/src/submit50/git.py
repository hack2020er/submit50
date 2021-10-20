import contextlib
import logging
import os
import subprocess
import tempfile


class GitClient:
    def __init__(self, repo, git_host='git@github.com:'):
        self.git_host = os.getenv('SUBMIT50_GIT_HOST', git_host)
        self.repo = repo
        self.git_dir = None

class AssignmentTemplateGitClient(GitClient):
    @contextlib.contextmanager
    def clone(self):
        """
        Clones self.repo into a temporary directory.
        """
        remote = os.path.join(self.git_host, self.repo)
        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                clone(['--depth', '1', '--quiet', remote, temp_dir])
            except subprocess.CalledProcessError as exc:
                logging.debug(exc, exc_info=True)
                raise RuntimeError(f'Failed to clone "{remote}".')
            yield temp_dir

class StudentAssignmentGitClient(GitClient):
    def __init__(self, username, *args, **kwargs):
        self.username = username
        super().__init__(*args, **kwargs)
        self.configs = self._default_configs()

    @contextlib.contextmanager
    def clone_bare(self):
        """
        Clones self.repo as a bare repository into a temporary directory and sets GIT_DIR to this
        temporary directory.
        """
        remote = os.path.join(self.git_host, self.repo)
        with tempfile.TemporaryDirectory() as git_dir:
            try:
                self._clone(['--bare', '--quiet', remote, git_dir])
            except subprocess.CalledProcessError as exc:
                logging.debug(exc, exc_info=True)
                raise RuntimeError(f'Failed to clone "{remote}".\nPlease make sure you accepted the assignment invite on the problem set page.')
            self.git_dir = git_dir
            yield git_dir

    def add(self):
        try:
            self._add_all()
            return self._ls_files()
        except subprocess.CalledProcessError as exc:
            logging.debug(exc, exc_info=True)
            raise RuntimeError('Failed to ready files for submission.')

    def commit_push(self):
        try:
            self._commit()
            self._push()
        except subprocess.CalledProcessError as exc:
            logging.debug(exc, exc_info=True)
            raise RuntimeError('Failed to submit.')

    def _clone(self, args):
        return self._git(['clone', *args])

    def _add_all(self):
        return self._git(['add', '--all'])

    def _ls_files(self):
        return sorted(self._git(['ls-files']).decode().split())

    def _commit(self):
        return self._git(['commit', '--allow-empty', '--message', 'Automated commit by submit50'])

    def _push(self):
        current_branch = self._current_branch()
        return self._git(['push', '--quiet', 'origin', current_branch])

    def _current_branch(self):
        return self._git(['branch', '--show-current']).decode().rstrip()

    def _git(self, args):
        git_dir = ['--git-dir', self.git_dir] if self.git_dir else []
        return git([*git_dir, '--work-tree', os.getcwd(), *self.configs, *args])

    def _default_configs(self):
        """
        Returns a list of git command-line arguments that configure user.name, user.email, and
        credential.helper.
        """
        configs = []
        if user_name_not_configured():
            configs.extend(['-c', f'user.name={self.username}'])

        if user_email_not_configured():
            configs.extend(['-c', f'user.email={self.username}@users.noreply.github.com'])

        if credential_helper_not_configured():
            configs.extend(['-c', 'credential.helper=cache'])

        return configs

def assert_git_installed():
    """
    Ensures that git is installed and is on PATH and raises a RuntimeError if not.
    """
    try:
        git(['--version'])
    except FileNotFoundError as exc:
        logging.debug(exc, exc_info=True)
        raise RuntimeError('It looks like git is not installed. Please install git then try again.')

def clone(args):
    return git(['clone', *args])

def user_name_not_configured():
    return not_configured('user.name')

def user_email_not_configured():
    return not_configured('user.email')

def credential_helper_not_configured():
    return not_configured('credential.helper')

def not_configured(key):
    try:
        return config(['--get', key])
    except subprocess.CalledProcessError as exc:
        logging.debug(exc, exc_info=True)
        return True
    return False

def config(args):
    return git(['config', *args])

def git(args):
    return subprocess.check_output(['git', *args])
