import cProfile
import iacli.ia_upload

argv = ['upload', '--verbose', 'jj-test-big-item-test', 'd.tar']
cProfile.run(iacli.ia_upload.main(argv))
