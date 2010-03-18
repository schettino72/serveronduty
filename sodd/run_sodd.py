from sodd.main import run_ci

if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print 'usage: python sodd.py <project.yaml>'
    proj_file = sys.argv[1]
    run_ci(proj_file)
