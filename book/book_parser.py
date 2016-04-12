# book_parser.py

from calibre.ptempfile import TemporaryDirectory

from unpack_structure import fileNames
from mobi_sectioner import Sectionizer
from mobi_header import MobiHeader
from mobi_split import mobi_split


class BookParser(object):
    def __init__(self, book_path):
        self._book_path = book_path

    def unpackBook(infile, outdir):
        DUMP = True
        WRITE_RAW_DATA = True

        infile = unicode_str(infile)
        outdir = unicode_str(outdir)

        files = fileNames(infile, outdir)

        # process the PalmDoc database header and verify it is a mobi
        sect = Sectionizer(infile)
        if sect.ident != b'BOOKMOBI' and sect.ident != b'TEXtREAd':
            raise unpackException('Invalid file format')
        if DUMP:
            sect.dumppalmheader()
        else:
            print("Palm DB type: %s, %d sections." % (sect.ident.decode('utf-8'),sect.num_sections))

        # scan sections to see if this is a compound mobi file (K8 format)
        # and build a list of all mobi headers to process.
        mhlst = []
        mh = MobiHeader(sect,0)
        # if this is a mobi8-only file hasK8 here will be true
        mhlst.append(mh)
        K8Boundary = -1

        if mh.isK8():
            print("Unpacking a KF8 book...")
            hasK8 = True
        else:
            # This is either a Mobipocket 7 or earlier, or a combi M7/KF8
            # Find out which
            hasK8 = False
            for i in range(len(sect.sectionoffsets)-1):
                before, after = sect.sectionoffsets[i:i+2]
                if (after - before) == 8:
                    data = sect.loadSection(i)
                    if data == K8_BOUNDARY:
                        sect.setsectiondescription(i,"Mobi/KF8 Boundary Section")
                        mh = MobiHeader(sect,i+1)
                        hasK8 = True
                        mhlst.append(mh)
                        K8Boundary = i
                        break
            if hasK8:
                print("Unpacking a Combination M{0:d}/KF8 book...".format(mh.version))
            else:
                print("Unpacking a Mobipocket {0:d} book...".format(mh.version))

        if hasK8:
            files.makeK8Struct()

        process_all_mobi_headers(files, apnxfile, sect, mhlst, K8Boundary, False, '2', False)

        if DUMP:
            sect.dumpsectionsinfo()
        return