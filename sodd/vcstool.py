import os
import re


class VcsTool(object):
    '''Basic useage:

    '''
    def __init__(self, url, user='', password='', revision_start=1):
        self.url = url
        self.user = user
        self.password = password
        self.revision_start = revision_start

    def makeWorkingCopy(self, dir_):
         # dir_ url should be: /path/to/svn/project
         # 
         #dir_ = self._checkDir(dir_)
        self.workingDir = dir_
	if os.path.exists(dir_):
		return

        cmdline = 'svn co %s ' % self.url
        if self.user:
            cmdline += '--username %s' % self.user
            if self.password:
                cmdline += '--password %s' % self.password
        cmdline += dir_
        if os.system(cmdline) == 0:
            self.workingDir = dir_


    def getRevisionNumbers(self, revision_from=None):
        if revision_from is None or revision_from < self.revision_start:
            revision_from = self.revision_start
        log_infos = self._getRevisionInfos(revision_from)
        res = [item['revision'][1:] for item in log_infos if item.get('revision', None)]
        return res

    def export(self, revision_num, destination_dir):
        # need to check the d_dir
        cmdline = 'svn export --force -r %s %s %s' % (revision_num, self.workingDir, destination_dir)
        if os.system(cmdline) != 0:
            # some bad things happened
            pass
        else:
            pass

    def _getRevisionInfos(self, from_):
        '''get infos from from_ to latest revision
        '''
        cmdline1 = "svn info %s | grep Revision | awk -F ': ' '{print $2}'" % self.workingDir
        cmdline2 = "svn log --limit 10 -r %s:HEAD %s" % (from_, self.workingDir)
        pattern = "(?P<revision>r\d+) \| (?P<author>\w+) \| (?P<datetime>[^|]+) \|.*"
        result = []
        # First, need to update working copy
        os.system('svn up %s' % self.workingDir)
        # Than, get the where we are
        pipe = os.popen(cmdline2)
        latest_num = pipe.readlines()[0]
        pipe.close()
        #
        if latest_num < from_ or latest_num > from_ + 100:
            # raise
            pass
        pipe = os.popen(cmdline2)
        logs = pipe.readlines()
        for line in logs:
           res = re.match(pattern, line)
           if res and res.groupdict():
               result.append(res.groupdict())
        pipe.close()

        # before return
        return result

    def _checkDir(self, dir_):
        #if dir_.endswith('/')
        return dir_
