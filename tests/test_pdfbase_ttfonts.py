
"""Test TrueType font subsetting & embedding code.

This test uses a sample font (Vera.ttf) taken from Bitstream which is called Vera
Serif Regular and is covered under the license in ../fonts/bitstream-vera-license.txt.
"""
from reportlab.lib.testutils import setOutDir,makeSuiteForClasses, outputfile, printLocation, NearTestCase, rlSkipUnless
if __name__=='__main__':
    setOutDir(__name__)
import unittest
from io import BytesIO
from reportlab.pdfgen.canvas import Canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.pdfdoc import PDFDocument, PDFError
from reportlab.pdfbase.ttfonts import TTFont, TTFontFace, TTFontFile, TTFOpenFile, \
                                      TTFontParser, TTFontMaker, TTFError, \
                                      makeToUnicodeCMap, \
                                      FF_SYMBOLIC, FF_NONSYMBOLIC, \
                                      calcChecksum, add32, uharfbuzz, shapeFragWord, \
                                      ShapedFragWord, ShapedStr, ShapeData
import zlib, bz2, base64
from reportlab import rl_config
from reportlab.lib.utils import int2Byte
from reportlab.lib.abag import ABag

def utf8(code):
    "Convert a given UCS character index into UTF-8"
    return chr(code).encode('utf8')

def _simple_subset_generation(fn,npages,alter=0,fonts=('Vera','VeraBI')):
    c = Canvas(outputfile(fn))
    c.setFont('Helvetica', 30)
    c.drawString(100,700, 'Unicode TrueType Font Test %d pages' % npages)
    # Draw a table of Unicode characters
    for p in range(npages):
        for fontName in fonts:
            c.setFont(fontName, 10)
            for i in range(32):
                for j in range(32):
                    ch = chr(i * 32 + j+p*alter)
                    c.drawString(80 + j * 13 + int(j / 16.0) * 4, 600 - i * 13 - int(i / 8.0) * 8, ch)
        c.showPage()
    c.save()

def show_all_glyphs(fn,fontName='Vera'):
    c = Canvas(outputfile(fn))
    c.setFont('Helvetica', 20)
    c.drawString(72,c._pagesize[1]-30, 'Unicode TrueType Font Test %s' % fontName)
    from reportlab.pdfbase.pdfmetrics import _fonts
    font = _fonts[fontName]
    doc = c._doc
    kfunc = font.face.charToGlyph.keys
    for s in sorted(list(kfunc())):
        if s<0x10000:
            font.splitString(chr(s),doc)
    state = font.state[doc]
    cn = {}
    #print('len(assignments)=%d'%  len(state.assignments))
    nzero = 0
    ifunc = state.assignments.items
    for code, n in sorted(list(ifunc())):
        if code==0: nzero += 1
        cn[n] = chr(code)
    if nzero>1: print('%s there were %d zero codes' % (fontName,nzero))


    ymin = 10*12
    y = y0 = c._pagesize[1] - 72
    for nss,subset in enumerate(state.subsets):
        if y<ymin:
            c.showPage()
            y = y0
        c.setFont('Helvetica', 10)
        x = 72
        c.drawString(x,y,'Subset %d len=%d' % (nss,len(subset)))
        #print('Subset %d len=%d' % (nss,len(subset)))
        c.setFont(fontName, 10)
        for i, code in enumerate(subset):
            if i%32 == 0:
                y -= 12
                x = 72
            c.drawString(x,y,chr(code))
            x += 13
        y -= 18

    c.showPage()
    c.save()

class TTFontsTestCase(unittest.TestCase):
    "Make documents with TrueType fonts"

    def testTTF(self):
        "Test PDF generation with TrueType fonts"
        pdfmetrics.registerFont(TTFont("Vera", "Vera.ttf"))
        pdfmetrics.registerFont(TTFont("VeraBI", "VeraBI.ttf"))
        try:
            pdfmetrics.registerFont(TTFont("DejaVuSans", "DejaVuSans.ttf"))
        except:
            pass
        else:
            show_all_glyphs('test_pdfbase_ttfonts_dejavusans.pdf',fontName='DejaVuSans')
        show_all_glyphs('test_pdfbase_ttfonts_vera.pdf',fontName='Vera')
        _simple_subset_generation('test_pdfbase_ttfonts1.pdf',1)
        _simple_subset_generation('test_pdfbase_ttfonts3.pdf',3)
        _simple_subset_generation('test_pdfbase_ttfonts35.pdf',3,5)

        # Do it twice with the same font object
        c = Canvas(outputfile('test_pdfbase_ttfontsadditional.pdf'))
        # Draw a table of Unicode characters
        c.setFont('Vera', 10)
        c.drawString(100, 700, b'Hello, ' + utf8(0xffee))
        c.save()

    def testSameTTFDifferentName(self):
        "Test PDF generation with TrueType fonts"
        pdfmetrics.registerFont(TTFont("Vera", "Vera.ttf"))
        pdfmetrics.registerFont(TTFont("MyVera", "Vera.ttf"))

        # Do it twice with the same font object
        c = Canvas(outputfile('test_pdfbase_ttfontsduplicate.pdf'))
        # Draw a table of Unicode characters
        c.setFont('Vera', 10)
        c.drawString(100, 700, b'Hello World')
        c.setFont('MyVera', 10)
        c.drawString(100, 688, b'Hello World')
        c.save()

class TTFontFileTestCase(NearTestCase):
    "Tests TTFontFile, TTFontParser and TTFontMaker classes"

    def testFontFileFailures(self):
        "Tests TTFontFile constructor error checks"
        self.assertRaises(TTFError, TTFontFile, "nonexistent file")
        self.assertRaises(TTFError, TTFontFile, BytesIO(b""))
        self.assertRaises(TTFError, TTFontFile, BytesIO(b"invalid signature"))
        self.assertRaises(TTFError, TTFontFile, BytesIO(b"OTTO - OpenType not supported yet"))
        self.assertRaises(TTFError, TTFontFile, BytesIO(b"\0\1\0\0"))

    def testFontFileReads(self):
        "Tests TTFontParset.read_xxx"

        class FakeTTFontFile(TTFontParser):
            def __init__(self, data):
                self._ttf_data = data
                self._pos = 0

        ttf = FakeTTFontFile(b"\x81\x02\x03\x04" b"\x85\x06" b"ABCD" b"\x7F\xFF" b"\x80\x00" b"\xFF\xFF")
        self.assertEqual(ttf.read_ulong(), 0x81020304) # big-endian
        self.assertEqual(ttf._pos, 4)
        self.assertEqual(ttf.read_ushort(), 0x8506)
        self.assertEqual(ttf._pos, 6)
        self.assertEqual(ttf.read_tag(), 'ABCD')
        self.assertEqual(ttf._pos, 10)
        self.assertEqual(ttf.read_short(), 0x7FFF)
        self.assertEqual(ttf.read_short(), -0x8000)
        self.assertEqual(ttf.read_short(), -1)

    def testFontFile(self):
        "Tests TTFontFile and TTF parsing code"
        ttf = TTFontFile("Vera.ttf")
        self.assertEqual(ttf.name, b"BitstreamVeraSans-Roman")
        self.assertEqual(ttf.flags, FF_SYMBOLIC)
        self.assertEqual(ttf.italicAngle, 0.0)
        self.assertNear(ttf.ascent,759.765625)
        self.assertNear(ttf.descent,-240.234375)
        self.assertEqual(ttf.capHeight, 759.765625)
        self.assertNear(ttf.bbox, [-183.10546875, -235.83984375, 1287.109375, 928.22265625])
        self.assertEqual(ttf.stemV, 87)
        self.assertEqual(ttf.defaultWidth, 600.09765625)

    def testAdd32(self):
        "Test add32"
        self.assertEqual(add32(10, -6), 4)
        self.assertEqual(add32(6, -10), -4&0xFFFFFFFF)
        self.assertEqual(add32(0x80000000, -1), 0x7FFFFFFF)
        self.assertEqual(add32(0x7FFFFFFF, 1), 0x80000000)

    def testChecksum(self):
        "Test calcChecksum function"
        self.assertEqual(calcChecksum(b""), 0)
        self.assertEqual(calcChecksum(b"\1"), 0x01000000)
        self.assertEqual(calcChecksum(b"\x01\x02\x03\x04\x10\x20\x30\x40"), 0x11223344)
        self.assertEqual(calcChecksum(b"\x81"), 0x81000000)
        self.assertEqual(calcChecksum(b"\x81\x02"), 0x81020000)
        self.assertEqual(calcChecksum(b"\x81\x02\x03"), 0x81020300)
        self.assertEqual(calcChecksum(b"\x81\x02\x03\x04"), 0x81020304)
        self.assertEqual(calcChecksum(b"\x81\x02\x03\x04\x05"), 0x86020304)
        self.assertEqual(calcChecksum(b"\x41\x02\x03\x04\xD0\x20\x30\x40"), 0x11223344)
        self.assertEqual(calcChecksum(b"\xD1\x02\x03\x04\x40\x20\x30\x40"), 0x11223344)
        self.assertEqual(calcChecksum(b"\x81\x02\x03\x04\x90\x20\x30\x40"), 0x11223344)
        self.assertEqual(calcChecksum(b"\x7F\xFF\xFF\xFF\x00\x00\x00\x01"), 0x80000000)

    def testFontFileChecksum(self):
        "Tests TTFontFile and TTF parsing code"
        F = TTFOpenFile("Vera.ttf")[1].read()
        TTFontFile(BytesIO(F), validate=1) # should not fail
        F1 = F[:12345] + b"\xFF" + F[12346:] # change one byte
        self.assertRaises(TTFError, TTFontFile, BytesIO(F1), validate=1)
        F1 = F[:8] + b"\xFF" + F[9:] # change one byte
        self.assertRaises(TTFError, TTFontFile, BytesIO(F1), validate=1)

    def testSubsetting(self):
        "Tests TTFontFile and TTF parsing code"
        ttf = TTFontFile("Vera.ttf")
        subset = ttf.makeSubset([0x41, 0x42])
        subset = TTFontFile(BytesIO(subset), 0)
        for tag in ('cmap', 'head', 'hhea', 'hmtx', 'maxp', 'name', 'OS/2',
                    'post', 'cvt ', 'fpgm', 'glyf', 'loca', 'prep'):
            self.assertTrue(subset.get_table(tag))

        subset.seek_table('loca')
        for n in range(4):
            pos = subset.read_ushort()    # this is actually offset / 2
            self.assertFalse(pos % 2 != 0, "glyph %d at +%d should be long aligned" % (n, pos * 2))

        self.assertEqual(subset.name, b"BitstreamVeraSans-Roman")
        self.assertEqual(subset.flags, FF_SYMBOLIC)
        self.assertEqual(subset.italicAngle, 0.0)
        self.assertNear(subset.ascent,759.765625)
        self.assertNear(subset.descent,-240.234375)
        self.assertEqual(subset.capHeight, 759.765625)
        self.assertNear(subset.bbox, [-183.10546875, -235.83984375, 1287.109375, 928.22265625])
        self.assertEqual(subset.stemV, 87)

    def testFontMaker(self):
        "Tests TTFontMaker class"
        ttf = TTFontMaker()
        ttf.add("ABCD", b"xyzzy")
        ttf.add("QUUX", b"123")
        ttf.add("head", b"12345678xxxx")
        stm = ttf.makeStream()
        ttf = TTFontParser(BytesIO(stm), 0)
        self.assertEqual(ttf.get_table("ABCD"), b"xyzzy")
        self.assertEqual(ttf.get_table("QUUX"), b"123")


class TTFontFaceTestCase(unittest.TestCase):
    "Tests TTFontFace class"

    def testAddSubsetObjects(self):
        "Tests TTFontFace.addSubsetObjects"
        face = TTFontFace("Vera.ttf")
        doc = PDFDocument()
        fontDescriptor = face.addSubsetObjects(doc, "TestFont", [ 0x78, 0x2017 ])
        fontDescriptor = doc.idToObject[fontDescriptor.name].dict
        self.assertEqual(fontDescriptor['Type'], '/FontDescriptor')
        self.assertEqual(fontDescriptor['Ascent'], face.ascent)
        self.assertEqual(fontDescriptor['CapHeight'], face.capHeight)
        self.assertEqual(fontDescriptor['Descent'], face.descent)
        self.assertEqual(fontDescriptor['Flags'], (face.flags & ~FF_NONSYMBOLIC) | FF_SYMBOLIC)
        self.assertEqual(fontDescriptor['FontName'], "/TestFont")
        self.assertEqual(fontDescriptor['FontBBox'].sequence, face.bbox)
        self.assertEqual(fontDescriptor['ItalicAngle'], face.italicAngle)
        self.assertEqual(fontDescriptor['StemV'], face.stemV)
        fontFile = fontDescriptor['FontFile2']
        fontFile = doc.idToObject[fontFile.name]
        self.assertTrue(fontFile.content != "")


class TTFontTestCase(NearTestCase):
    "Tests TTFont class"

    def testStringWidth(self):
        "Test TTFont.stringWidth"
        font = TTFont("Vera", "Vera.ttf")
        self.assertTrue(font.stringWidth("test", 10) > 0)
        width = font.stringWidth(utf8(0x2260) * 2, 1000)
        expected = font.face.getCharWidth(0x2260) * 2
        self.assertNear(width,expected)

    def testTTFontFromBytesIO(self):
        "Test loading TTFont from in-memory file"
        # Direct source: https://github.com/tmbdev/hocr-tools/blob/master/hocr-pdf
        # Glyphless variation of vedaal's invisible font retrieved from
        # http://www.angelfire.com/pr/pgpf/if.html, which says:
        # 'Invisible font' is unrestricted freeware. Enjoy, Improve, Distribute freely
        font = """
        eJzdlk1sG0UUx/+zs3btNEmrUKpCPxikSqRS4jpfFURUagmkEQQoiRXgAl07Y3vL2mvt2ml8APXG
        hQPiUEGEVDhWVHyIC1REPSAhBOWA+BCgSoULUqsKcWhVBKjhzfPU+VCi3Flrdn7vzZv33ryZ3TUE
        gC6chsTx8fHck1ONd98D0jnS7jn26GPjyMIleZhk9fT0wcHFl1/9GRDPkTxTqHg1dMkzJH9CbbTk
        xbWlJfKEdB+Np0pBswi+nH/Nvay92VtfJp4nvEztUJkUHXsdksUOkveXK/X5FNuLD838ICx4dv4N
        I1e8+ZqbxwCNP2jyqXoV/fmhy+WW/2SqFsb1pX68SfEpZ/TCrI3aHzcP//jitodvYmvL+6Xcr5mV
        vb1ScCzRnPRPfz+LsRSWNasuwRrZlh1sx0E8AriddyzEDfE6EkglFhJDJO5u9fJbFJ0etEMB78D5
        4Djm/7kjT0wqhSNURyS+u/2MGJKRu+0ExNkrt1pJti9p2x6b3TBJgmUXuzgnDmI8UWMbkVxeinCw
        Mo311/l/v3rF7+01D+OkZYE0PrbsYAu+sSyxU0jLLtIiYzmBrFiwnCT9FcsdOOK8ZHbFleSn0znP
        nDCnxbnAnGT9JeYtrP+FOcV8nTlNnsoc3bBAD85adtCNRcsSffjBsoseca/lBE7Q09LiJOm/ttyB
        0+IqcwfncJt5q4krO5k7jV7uY+5m7mPebuLKUea7iHvk48w72OYF5rvZT8C8k/WvMN/Dc19j3s02
        bzPvZZv3me9j/ox5P9t/xdzPzPVJcc7yGnPL/1+GO1lPVTXM+VNWOTRRg0YRHgrUK5yj1kvaEA1E
        xAWiCtl4qJL2ADKkG6Q3XxYjzEcR0E9hCj5KtBd1xCxp6jV5mKP7LJBr1nTRK2h1TvU2w0akCmGl
        5lWbBzJqMJsdyaijQaCm/FK5HqspHetoTtMsn4LO0T2mlqcwmlTVOT/28wGhCVKiNANKLiJRlxqB
        F603axQznIzRhDSq6EWZ4UUs+xud0VHsh1U1kMlmNwu9kTuFaRqpURU0VS3PVmZ0iE7gct0MG/8+
        2fmUvKlfRLYmisd1w8pk1LSu1XUlryM1MNTH9epTftWv+16gIh1oL9abJZyjrfF5a4qccp3oFAcz
        Wxxx4DpvlaKKxuytRDzeth5rW4W8qBFesvEX8RFRmLBHoB+TpCmRVCCb1gFCruzHqhhW6+qUF6tC
        pL26nlWN2K+W1LhRjxlVGKmRTFYVo7CiJug09E+GJb+QocMCPMWBK1wvEOfRFF2U0klK8CppqqvG
        pylRc2Zn+XDQWZIL8iO5KC9S+1RekOex1uOyZGR/w/Hf1lhzqVfFsxE39B/ws7Rm3N3nDrhPuMfc
        w3R/aE28KsfY2J+RPNp+j+KaOoCey4h+Dd48b9O5G0v2K7j0AM6s+5WQ/E0wVoK+pA6/3bup7bJf
        CMGjwvxTsr74/f/F95m3TH9x8o0/TU//N+7/D/ScVcA=
        """.encode('latin1')
        uncompressed = zlib.decompress(base64.decodebytes(font))
        ttf = BytesIO(uncompressed)
        setattr(ttf ,"name", "(invisible.ttf)")
        font = TTFont('invisible', ttf)
        for coord in font.face.bbox:
            self.assertEqual(coord, 0)
        pdfmetrics.registerFont(font)
        _simple_subset_generation('test_pdfbase_ttffonts_invisible.pdf',2,fonts=('invisible',))

    def testSplitString(self):
        "Tests TTFont.splitString"
        doc = PDFDocument()
        font = TTFont("Vera", "Vera.ttf", asciiReadable=True)
        T = list(range(256))
        for c in sorted(font.face.charToGlyph):
            if c not in T: T.append(c)
        text = "".join(map(chr,T))
        #we ignore rserveTTFNotDef by assuming it's always True
        #PDFUA forbids index 0(.notdef) in strings
        chunks = [(0,
            b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
            b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00 !"#$%&\''
            b'()*+,-./0123456789:;<=>?@ABCDEFGHIJKLMNOPQRSTUVWXYZ[\\]^_`abcdefghijklmno'
            b'pqrstuvwxyz{|}~\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
            b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
            b'\x00\x00\x00\x00 \x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b\x0c\r\x0e\x0f'
            b'\x10\x11\x12\x13\x14\x15\x16\x17\x18\x19\x1a\x1b\x1c\x1d\x1e\x1f'
            b'\x80\x81\x82\x83\x84\x85\x86\x87\x88\x89\x8a\x8b\x8c\x8d\x8e\x8f'
            b'\x90\x91\x92\x93\x94\x95\x96\x97\x98\x99\x9a\x9b\x9c\x9d\x9e\x9f'
            b'\xa0\xa1\xa2\xa3\xa4\xa5\xa6\xa7\xa8\xa9\xaa\xab\xac\xad\xae\xaf'
            b'\xb0\xb1\xb2\xb3\xb4\xb5\xb6\xb7\xb8\xb9\xba\xbb\xbc\xbd\xbe\xbf'
            b'\xc0\xc1\xc2\xc3\xc4\xc5\xc6\xc7\xc8\xc9\xca\xcb\xcc\xcd\xce\xcf'
            b'\xd0\xd1\xd2\xd3\xd4\xd5\xd6\xd7\xd8\xd9\xda\xdb\xdc\xdd\xde\xdf'
            b'\xe0\xe1\xe2\xe3\xe4\xe5\xe6\xe7\xe8\xe9\xea\xeb\xec\xed\xee\xef'
            b'\xf0\xf1\xf2\xf3\xf4\xf5\xf6\xf7\xf8\xf9\xfa\xfb\xfc\xfd\xfe\xff'),
         (1,
            b'\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b\x0c\r\x0e\x0f\x10\x11\x12\x13\x14'
            b'\x15\x16\x17\x18\x19\x1a\x1b\x1c')]
        self.assertEqual(font.splitString(text, doc), chunks)
        # Do it twice
        self.assertEqual(font.splitString(text, doc), chunks)

    def testSplitStringSpaces(self):
        # In order for justification (word spacing) to work, the space
        # glyph must have a code 32, and no other character should have
        # that code in any subset, or word spacing will be applied to it.

        doc = PDFDocument()
        font = TTFont("Vera", "Vera.ttf")
        text = b"".join(utf8(i) for i in range(512, -1, -1))
        chunks = font.splitString(text, doc)
        state = font.state[doc]
        self.assertEqual(state.assignments[32], 32)
        self.assertEqual(state.subsets[0][32], 32)

    def testSubsetInternalName(self):
        "Tests TTFont.getSubsetInternalName"
        doc = PDFDocument()
        font = TTFont("Vera", "Vera.ttf")
        # Actually generate some subsets
        text = b"".join(utf8(i) for i in range(513))
        font.splitString(text, doc)
        self.assertRaises(IndexError, font.getSubsetInternalName, -1, doc)
        self.assertRaises(IndexError, font.getSubsetInternalName, 3, doc)
        self.assertEqual(font.getSubsetInternalName(0, doc), "/F1+0")
        self.assertEqual(doc.delayedFonts, [font])

    def testAddObjectsEmpty(self):
        "TTFont.addObjects should not fail when no characters were used"
        font = TTFont("Vera", "Vera.ttf")
        doc = PDFDocument()
        font.addObjects(doc)

    def no_longer_testAddObjectsResets(self):
        "Test that TTFont.addObjects resets the font"
        # Actually generate some subsets
        doc = PDFDocument()
        font = TTFont("Vera", "Vera.ttf")
        font.splitString('a', doc)            # create some subset
        doc = PDFDocument()
        font.addObjects(doc)
        self.assertEqual(font.frozen, 0)
        self.assertEqual(font.nextCode, 0)
        self.assertEqual(font.subsets, [])
        self.assertEqual(font.assignments, {})
        font.splitString('ba', doc)           # should work

    def testParallelConstruction(self):
        "Test that TTFont can be used for different documents at the same time"
        doc1 = PDFDocument()
        doc2 = PDFDocument()
        font = TTFont("Vera", "Vera.ttf", asciiReadable=1)
        self.assertEqual(font.splitString('hello ', doc1), [(0, b'hello ')])
        self.assertEqual(font.splitString('hello ', doc2), [(0, b'hello ')])
        self.assertEqual(font.splitString('\xae\xab', doc1), [(0, b'\x01\x02')])
        self.assertEqual(font.splitString('\xab\xae', doc2), [(0, b'\x01\x02')])
        self.assertEqual(font.splitString('\xab\xae', doc1), [(0, b'\x02\x01')])
        self.assertEqual(font.splitString('\xae\xab', doc2), [(0, b'\x02\x01')])
        font.addObjects(doc1)
        #after addObjects doc1 state is no longer valid, doc2 should be OK
        self.assertEqual(font.splitString('\xae\xab', doc2), [(0, b'\x02\x01')])
        font.addObjects(doc2)

    def testAddObjects(self):
        "Test TTFont.addObjects"
        # Actually generate some subsets
        doc = PDFDocument()
        font = TTFont("Vera", "Vera.ttf", asciiReadable=1)
        font.splitString('a', doc)            # create some subset
        internalName = font.getSubsetInternalName(0, doc)[1:]
        font.addObjects(doc)
        pdfFont = doc.idToObject[internalName]
        self.assertEqual(doc.idToObject['BasicFonts'].dict[internalName], pdfFont)
        self.assertEqual(pdfFont.Name, internalName)
        self.assertEqual(pdfFont.BaseFont, "AAAAAA+BitstreamVeraSans-Roman")
        self.assertEqual(pdfFont.FirstChar, 0)
        self.assertEqual(pdfFont.LastChar, 127)
        self.assertEqual(len(pdfFont.Widths.sequence), 128)
        toUnicode = doc.idToObject[pdfFont.ToUnicode.name]
        self.assertTrue(toUnicode.content != "")
        fontDescriptor = doc.idToObject[pdfFont.FontDescriptor.name]
        self.assertEqual(fontDescriptor.dict['Type'], '/FontDescriptor')

    def testMakeToUnicodeCMap(self):
        "Test makeToUnicodeCMap"
        self.assertEqual(makeToUnicodeCMap("TestFont", [ 0x1234, 0x4321, 0x4242 ]),
"""/CIDInit /ProcSet findresource begin
12 dict begin
begincmap
/CIDSystemInfo
<< /Registry (TestFont)
/Ordering (TestFont)
/Supplement 0
>> def
/CMapName /TestFont def
/CMapType 2 def
1 begincodespacerange
<00> <02>
endcodespacerange
3 beginbfchar
<00> <1234>
<01> <4321>
<02> <4242>
endbfchar
endcmap
CMapName currentdict /CMap defineresource pop
end
end""")

    def hbIfaceTest(self, ttf, text, exLen, exText, exShapedData):
        fontName = ttf.fontName
        fontSize = 30
        pdfmetrics.registerFont(ttf)
        w = [pdfmetrics.stringWidth(text,fontName,fontSize),(ABag(fontName=fontName,fontSize=fontSize),text)]
        new = shapeFragWord(w)
        ttf.unregister()
        self.assertEqual(len(new),2,'expected a len of 2')
        self.assertTrue(isinstance(new,ShapedFragWord),f'returned list class is {new.__class__.__name__} not expected ShapedFragWord')
        self.assertEqual(new[0],exLen,f'new[0]={new[0]} not expected ={exLen}')
        self.assertTrue(isinstance(new[1][1],ShapedStr),f'returned str class is {new[1].__class__.__name__} not expected ShapedStr')
        self.assertTrue(new[1][1]==exText,'shaped string is wrong')
        self.assertEqual(new[1][1].__shapeData__,exShapedData, 'shape data is wrong')

    @rlSkipUnless(uharfbuzz,'no harfbuzz support')
    def test_hb_shape_change(self):
        ttf = hb_test_ttf()
        return self.hbIfaceTest(ttf,'\u1786\u17D2\u1793\u17B6\u17C6|', 44.22,'\ue000\ue001\u17c6|',
                                [ShapeData(cluster=0, x_advance=923, y_advance=0, x_offset=0, y_offset=0, width=923),
                                ShapeData(cluster=0, x_advance=0, y_advance=0, x_offset=-296, y_offset=-26, width=0),
                                ShapeData(cluster=4, x_advance=0, y_advance=0, x_offset=47, y_offset=-29, width=0),
                                ShapeData(cluster=5, x_advance=551, y_advance=0, x_offset=0, y_offset=0, width=551)])

    @rlSkipUnless(uharfbuzz,'no harfbuzz support')
    def test_hb_ligature(self):
        ttf = TTFont('Vera','Vera.ttf')
        #ligatures cause the standard length 133.2275390625 to be reduced to 130.78125
        return self.hbIfaceTest(ttf,'Aon Way',130.78125,'Aon Way',
                                [ShapeData(cluster=0, x_advance=675.29296875, y_advance=0, x_offset=0.0, y_offset=0, width=684.08203125),
                                ShapeData(cluster=1, x_advance=603.02734375, y_advance=0, x_offset=-8.7890625, y_offset=0, width=611.81640625),
                                ShapeData(cluster=2, x_advance=633.7890625, y_advance=0, x_offset=0.0, y_offset=0, width=633.7890625),
                                ShapeData(cluster=3, x_advance=317.87109375, y_advance=0, x_offset=0.0, y_offset=0, width=317.87109375),
                                ShapeData(cluster=4, x_advance=956.54296875, y_advance=0, x_offset=0.0, y_offset=0, width=988.76953125),
                                ShapeData(cluster=5, x_advance=581.0546875, y_advance=0, x_offset=-31.73828125, y_offset=0, width=612.79296875),
                                ShapeData(cluster=6, x_advance=591.796875, y_advance=0, x_offset=0.0, y_offset=0, width=591.796875)])

    @rlSkipUnless(uharfbuzz,'no harfbuzz support')
    def test_hb0(self):
        ttf = hb_test_ttf()
        try:
            text = '\u1786\u17D2\u1793\u17B6\u17C6|'
            #'\ue000\ue001\u17c6'
            fontName = ttf.fontName
            fontSize = 30
            pdfmetrics.registerFont(ttf)
            from reportlab.pdfgen.textobject import PDFTextObject
            from reportlab.pdfgen.canvas import Canvas
            canv = Canvas(outputfile('test_pdfbase_ttfonts_hb0.pdf'))
            ttf.splitString(text,canv._doc)
            w = [pdfmetrics.stringWidth(text,fontName,fontSize),(ABag(fontName=fontName,fontSize=fontSize),text)]
            new = shapeFragWord(w)
            canv.addLiteral(r"""
1 0 0 1 0 0 cm  BT /F1 12 Tf 14.4 TL ET
BT 1 0 0 1 0 0 Tm 1 0 0 1 36 806 Tm /F2+0 30 Tf 36 TL (\001\002\003\004\005) Tj /F3+0 12 Tf 14.4 TL ( '\\u1786\\u17d2\\u1793\\u17b6\\u17c6') Tj T* ET
q
.1 w
0 .501961 0 RG
n 63.69 750 m 63.69 786 l S
1 0 0 RG
n 54.81 750 m 54.81 786 l S
0 0 1 RG
n 53.4 750 m 53.4 786 l S
Q
BT 1 0 0 1 0 0 Tm 1 0 0 1 36 756 Tm /F2+0 30 Tf 36 TL (\006) Tj -0.78 Ts [296 (\007) -296] TJ -0.87 Ts [-47 (\005) 47] TJ .87 Ts (|) Tj /F3+0 12 Tf 14.4 TL ( '\\ue000\\ue001\\u17c6') Tj T* ET
BT 1 0 0 1 0 0 Tm 1 0 0 1 36 706 Tm /F2+0 30 Tf 36 TL (\006) Tj 1 0 0 1 54.81 705.22 Tm (\007) Tj 1 0 0 1 63.69 706 Tm 1 0 0 1 65.1 705.13 Tm (\005) Tj 1 0 0 1 63.49 706 Tm (|) Tj  ET
q
.1 w
0 .501961 0 RG
n 36 650 m 36 686 l S
Q
BT 1 0 0 1 0 0 Tm 1 0 0 1 36 656 Tm /F2+0 30 Tf 36 TL (|) Tj ET""")
            ttf._shaped = True
            canv.setFont(fontName,fontSize)
            t = canv.beginText(36, 626)
            t._textOut(new[1][1],False)
            code = t.getCode()
            excode = r'''BT 1 0 0 1 36 626 Tm /F2+0 30 Tf 36 TL (\006) Tj -0.78 Ts [296 (\007) -296] TJ -0.87 Ts [-47 (\005) 47] TJ (|) Tj ET'''
            canv.drawText(t)
            canv.showPage()
            canv.save()
            self.assertEqual(code,excode,'PDF _textOut is wrong')
        finally:
            ttf.unregister()

def hb_test_ttf(ttfn='hb-test'):
    #return TTFont(ttfn,'NotoSansKhmer-Regular.ttf')
    return TTFont(ttfn,
            BytesIO(bz2.decompress(base64.a85decode(r'''
                6<\%_0gSqh;d&_^k#q`bI"21rs8W-!s8W-!s8U^Ns8W-!=3b*]`,jh\T3pD8i0RO'#2LZ])_
                JAJ!!!C-`c0E5R5"e3$2UDddQL;]BnU2^)B&V&Bq^3sBo!TQ+:U/@)DopmBPHZqciCua"&/b
                P1dD)7)DhO`9c>beae6ui%2racJ,g"17[a<4!"Cb&%5Jcg#+@@Kd@^nu!.Y/:1h[)JRP\OUP
                <ki[)DoMQ!!!l@NALWG!#fN+)ItQX%5_`!UHf[s!,+YR.A<!Z2,>Qe-`2a-RAp%\TR'(YOu1
                EZ8VDD]VBMk9df9Cc!!#\M$qAZ0<:X^^!,1'h)3SCUBRg1M1h[)JRP\OUP<ki[)DoMQ!!!l@
                NALWG!#fN+)ItQX%5_`!UHf[s!(nL;"N"[fBFRnn,LjY@ANU\!b%@O";[lEh1sqC&(dgcP1c
                .&<7aqI6:K'c^1,K(VUI-2uUHj,q*qnFjau6#oT1)/b`]sXV\#si_$U?FKi8mEs(6Qa9(NNN
                qMIeUK%!.fe'<":[VomsHlf6sJd^J)hGp6l7HYjXINe9jiLN68nDGgM[/l'#M*9ek6QDIDMH
                7SU3Y8'$P&f2Tl.5]/-Qn\[.nPVd&^)n%kQr2`Y&Jed4b?;qhQt'^-`9XHHBEK?']YuFiC[T
                ?7ju'lI#j//DRb*uhgPdV8T$N:Fl&1-/"?1X=!a%==*o.$MeT1laOrGWX7!s8JJcQ+-/+r;O
                M[@4[`I26,ePU>#`R(TAm:0h)XDu*803FI<V`TY$9L'S^KK2CZ:D7IUIr#V6XOO&Q1R6&t:f
                BcUE/$Je6V9'mL/YEm%2kF!BYi#iGsGrIAsUEpY$o-99TfoCNcHu4m<m)s>K!6\3ZKDBNWl?
                u7RrO\53dq2dgji-^F#,K'm$%14B/RJ.*e:G?!16n;SM&:!q2L)WVm]WFKj3*9_F]KBlVJ_"
                >_g8<8#!,Pf;+Ue4YZgoM![H1lQ<omq:C\Xj]8_!QChLhpu*33.Xd@Ljn6(]<AqGe)9*HU0K
                8NLO2QIf?%F!\b6%_$\T.trPpJkZuoDm$Ap0(G$%d>B<=BrR,#T[\-<g9_3"MIo=:=o(IVd>
                5U[D\H<9nrHdQRfg;)K66T*:<<!J(2=C:i*$B8J]%$*RJ:;r(7`g-\^."X=,,X@c?*l$q8Te
                [Ku5%JU[N6A*2WNLZced)eB,4:@ibJf#OWgJ/;h6P78KYB;XKrFggG%jj?:r2C3:16_rYD!O
                -&QJm1VphpD)?[!9'i>M_:t&K_)A'&_6Uom]Q.Xi;dUJ^P@=PS(>1)F[k:06.Cs42C5=WHd<
                'tQ%#oQ'(Y%m01684?/_@-c+9gg'g$;cj96,j)ak?=X@)%EA3+/gj2[YlSt008^BrOL$6G/J
                R(h*_B/"!C$[.RHr60!fEV9jkl+$Rpt+`=[uh/:kI-_%/iU2(EgOh^S`.Wa"sboV-!DCT*)U
                ?3-X)'PK"aM8RGFNuWcO)G@5BpZ=2krUR57?UP3r$t?6:WiE',$AKb!B^9X'bKsCS7tHtq`g
                *jZE1#W/6^<M?'W=^sZ"K;Y",2:cW?*.BI`(1j'FeJO1"Su6"MggU-!;%)Eo7LPH&ubH$=gL
                [od"o'no=7o.jaRl'FPP.1%Jr!V.i1qUF;VqU(g4[90c0(LI^XO`'K5<OkYjCCprOc/[YXFa
                30Z/=`')U`#UeeG(q7GEH#7tOVCC04Cq,%NWXA-bJrTm>Ldp/B2*j5;LAKJFsJAjpDi4"F9m
                1<Alb"%6;/gE".Gs_S5V+609g,](D1k3!jqO<aN!r7KcW8JeqOIhA9=uP5fW0uB/%+HcDEF&
                *.mre9i=A.`K$8gaJmCU@!$eDrMa<pM],o)p@/KZRD`>2*^*kFT>f!B,LSh5R7<"e,2OE4Ol
                >RH/Zd#/DQJnCm?!VZ-35AI"^pK_TX`Sj-0Z3UYe$.Q\*(o)J\W?Q/g;L7`R,fJ;0oP=9\_*
                Dn\RNY1C<*^qQ>r5kjh6cVPJVo8Z@4OWN]5tBf'=W$>Bl&M)e&TKL3LXcY/n2h=?C?U-SQYR
                R/1E)i!HKRJ@gs&W6/8S)Nq+C-.K!J%A+jL#IP_)]=.+`Yl?EUa6*?aW:g4KhWGF2A?SE+WW
                O;$&2[nLnT/B1J',s4@9Yf'Vnp#,OSP=)`_b!.M@971'Wk=k0-\o3^VtNP4344.O'6LNh]%J
                TJ&lRj4KoIib_/X)@6[B1r>tA1jW-"/F\DrV*n>cLoB-6L:jTDLXSZMHC35&1*\GA&di6XmZ
                *KqN<-pODQT_J<\E-;_W8.<YHSmlAjXpS*##!q'"'C7Q3F%\T-.aA;iIT-K+@9f7=Quen9SS
                LDqa/FJclf%PWi#Zj-sWeL+.0b<SsEJg?V-7p`NcYCd!l1X7Ul!:_A\J=#;PTeFa.Lpo6U\&
                gD9m$R$QH0s0`k#0R>BHQnZ8:dJS]Y+AVe2i:Od.](LS_QC82\-3&R,Ze.RPE7/BaGPJ'5-R
                !)Ea"[--RafX)U9TpdBEc=)QARN.ks=*W<?<R^fjb@cu;TeL6^_,QE3o9:K5f[,%.-D\7-RQ
                S$^@TJn?(H*\N`;J>a_b@aH#],#Vko8uYp8r-"2sdRY(0>a1X/-8L[.?ia`N8nupUF)qFGCY
                ]),K,00(J_hu"5emYc&<8N$WqMU=_2<33ks7YADgH*X:P<Z=9uc*tfL%=`aNmI%7-01?Xk6>
                Rks>Kn_>HjnBB:ilq/Xc>!rlGGOYl[/6%l&uG3.gcB-d")XoN;L%j0209jlK0g+66Y0hC*!&
                ;$\.%mj-.;'c2n"s8;l\1=m%1]_AIlH\ftMgX@Jr:`s8^V%p6Z2_euO\QT94T'JjJ,'''
                ))))

def makeSuite():
    suite = makeSuiteForClasses(
        TTFontsTestCase,
        TTFontFileTestCase,
        TTFontFaceTestCase,
        TTFontTestCase)
    return suite


#noruntests
if __name__ == "__main__":
    unittest.TextTestRunner().run(makeSuite())
    printLocation()
