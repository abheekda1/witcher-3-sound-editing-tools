import sys
import os
import shutil
from xml.etree import ElementTree

XMLFILE = "soundbanksinfo.xml"

def main(argc, argv):
    if argc != 4:
        print "Usage: %s <SFX TYPE> <SUBSTRING> <SRC FILE>" % (os.path.basename(argv[0]))
        sys.exit(1)

    sfxtype = argv[1].strip().lower()
    substring = argv[2].strip().lower()
    srcfile = argv[3].strip()

    assert sfxtype, "Invalid SFX type"
    assert substring, "Invalid substring"
    assert srcfile, "Invalid source file"

    if srcfile.endswith(".wem"):
        ext = ".wem"
    else:
        raise NotImplementedError("File type is not supported")

    xml = ElementTree.parse(XMLFILE)
    root = xml.getroot()

    for entry in root[2]:
        if entry.tag == "File":
            try:
                id = int(entry.attrib["Id"])

                if entry.attrib["Language"] != "SFX":
                    raise ValueError

                shortname = entry[0]

                if shortname.tag != "ShortName":
                    raise ValueError
            except (KeyError, ValueError, IndexError):
                continue
            else:
                data = shortname.text.lower()

                if data.startswith(sfxtype + "\\") and substring in data:
                    shutil.copy(srcfile, "%i%s" % (id, ext))

if __name__ == "__main__":
    main(len(sys.argv), sys.argv)
