import os
import shutil
import subprocess

import py.test

import vcs


# create temporary folder that will get test data
def pytest_funcarg__testbin(request):
    def create_empty_folder():
        if os.path.exists('testbin'): shutil.rmtree('testbin')
        os.mkdir('testbin')
        return 'testbin'
    return request.cached_setup(setup=create_empty_folder,
                                teardown=shutil.rmtree, scope="session")


def pytest_generate_tests(metafunc):
    if TestVcs == metafunc.cls:
        for vcs_ in (vcs.HG, vcs.SVN, vcs.BZR):
            metafunc.addcall(id=vcs_.__name__,param=vcs_)

commit_2_msg = """commit no 2
has more than

one line and a blank line"""

# create repo
def pytest_funcarg__repo(request):
    # request.param is the vcs class to be used
    def create_repo():
        repo_path  = 'testbin/%s' % request.param.__name__
        if os.path.exists(repo_path): shutil.rmtree(repo_path)
        # create repo
        repo_source = request.param.init(repo_path)
        repo = request.param(repo_source, repo_path)
        # commit 0 - file1
        subprocess.call(['echo', 'hi'], stdout=open(repo_path + '/file1','w'))
        repo.add(repo_path + '/file1')
        repo.commit('initial commit')
        # commit 1 - file2
        subprocess.call(['echo', 'hello'], stdout=open(repo_path + '/file2','w'))
        repo.add(repo_path + '/file2')
        repo.commit(commit_2_msg)
        return repo

    def rm_repo(repo):
        shutil.rmtree('testbin/%s' % repo.__class__.__name__)
        if repo.source.startswith('file://'):
            source_path = repo.source[7:]
        else:
            source_path = repo.source
        if os.path.exists(source_path):
            shutil.rmtree(source_path)

    return request.cached_setup(
        setup=create_repo,
        teardown=rm_repo,
        scope="function")



class TestVcs(object):

    def test_clone(self, testbin, repo):
        clone_path = repo.work_path + '_clone'
        clone = repo.__class__(repo.source, clone_path)
        clone.clone()
        assert clone.is_repo(clone_path)


    def test_clone_dst_exist(self, testbin, repo):
        # an exception is raised if clone destination path exists.
        norepo_path = repo.work_path + 'no_repo'
        repo = repo.__class__(repo.source, norepo_path)
        os.mkdir(norepo_path)
        py.test.raises(Exception, repo.clone)


    def test_archive(self, testbin, repo):
        arch_path = repo.work_path + '_archive'
        repo.archive(str(1 + repo.rev_zero), arch_path)
        assert os.path.exists(arch_path + '/file1')
        assert os.path.exists(arch_path + '/file2')
        assert not repo.is_repo(arch_path)
        # overwrite folder and get non-tip
        repo.archive(str(0 + repo.rev_zero), arch_path)
        assert os.path.exists(arch_path + '/file1')
        assert not os.path.exists(arch_path + '/file2')
        assert not repo.is_repo(arch_path)


    def test_pull(self, testbin, repo):
        pull_path = repo.work_path + '_pull'
        clone = repo.__class__(repo.source, pull_path)
        clone.clone()
        # add one more changeset to trunk
        subprocess.call(['echo', 'hello'],
                        stdout=open(repo.work_path + '/more','w'))
        repo.add(repo.work_path + '/more')
        repo.commit('commit no 3')
        assert str(1 + repo.rev_zero) == clone.tip()
        clone.pull()
        assert str(2 + repo.rev_zero) == clone.tip()


    def test_get_new_revisions(self, testbin, repo):
        get_path = repo.work_path + '_get_revs'
        clone = repo.__class__(repo.source, get_path)
        clone.clone()
        # add one more changeset to trunk
        subprocess.call(['echo', 'hello'],
                        stdout=open(repo.work_path + '/more','w'))
        repo.add(repo.work_path + '/more')
        repo.commit('commit no 3')
        #
        new_revs = clone.get_new_revisions(str(0 + repo.rev_zero))
        assert str(1 + repo.rev_zero) == new_revs[0]['revision']
        assert "committer" in new_revs[0]
        assert commit_2_msg == new_revs[0]['comment']
        assert str(2 + repo.rev_zero) == new_revs[1]['revision']
        assert 2 == len(new_revs)

        # test get empty list
        new_revs2 = clone.get_new_revisions(str(2 + repo.rev_zero))
        assert 0 == len(new_revs2)

