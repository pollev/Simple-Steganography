#!/usr/bin/python
import struct
import os
import sys
import getopt

tmpFilePath = "tmpSecret.txt"

mode = None

bitlength = 0

pic = None
picName = ""
picSize = 0

secret = None
secretName = ""
secretSize = 0

out = None
outName = ""


def main(argv):

    # Parse arguments
    parseArgs(argv)

    if mode == "encode":
        encode()
    elif mode == "decode":
        decode()

    return

##########
# ENCODE #
##########


def encode():
    global secretName
    global picSize, secretSize
    picSize = int(os.stat(picName).st_size)
    secretSize = int(os.stat(secretName).st_size)

    # Patch secret file with size data
    tmp = open(tmpFilePath, "wb")
    sizebytes = struct.pack(">I", secretSize)
    # printByte = "".join(["\\x%02X" % ord(c) for c in sizebytes])
    printInfo("secret length: {}".format(secretSize))

    tmp.write(sizebytes)
    tmpSecretReader = open(secretName, "rb")
    tmpbyte = tmpSecretReader.read(1)
    while tmpbyte != "":
        tmp.write(tmpbyte)
        tmpbyte = tmpSecretReader.read(1)

    # Close patch reader and writer and reset secret name and size
    tmp.close()
    tmpSecretReader.close()
    secretName = tmpFilePath
    secretSize = os.stat(secretName).st_size

    global bitlength
    if(bitlength == -1):
        ratio = picSize // secretSize
        bitlength = 8 // ratio
        if bitlength == 0:
            bitlength = 1
        printInfo("")
        printInfo("Detected picture / secret ratio of {}. Using bit size of {}".format(ratio, bitlength))
        printInfo("")

    # Open file handles
    global pic, secret, out
    pic = open(picName, "rb")
    secret = open(secretName, "rb")
    out = open(outName, "wb")

    patchImage()
    return


def patchImage():
    try:
        offset = getPixelArrayOffset()
        # Write header to out
        pic.seek(0)
        header = pic.read(offset)
        out.write(header)
        # Jump to pixel array
        pic.seek(offset)
        # Iterate over pixel array and secret file
        rgb = pic.read(8 / bitlength)
        char = secret.read(1)
        bitindex = 0
        while len(rgb) == (8 / bitlength) and len(char) == 1:
            # printByte = "".join(["\\x%02X" % ord(c) for c in rgb])
            charOffset = 0
            for c in rgb:
                masked = c
                for i in range(0, bitlength, 1):
                    masked = writeBit(masked, i, readBit(char, charOffset * bitlength + i))
                out.write(masked)
                bitindex = bitindex + bitlength
                charOffset = charOffset + 1
            rgb = pic.read(8 / bitlength)
            char = secret.read(1)
        # display status
        if len(rgb) != (8 / bitlength):
            printInfo("ran out of image")
            sys.exit()
        else:
            printInfo("success adding secret to image")

        # append rest of image file
        appendLeftOverPic(rgb)
    finally:
        pic.close()
        secret.close()
        out.close()
        os.remove(tmpFilePath)
        printInfo("COMPLETED STEGANOGRAPHY")
    return


def appendLeftOverPic(rgb):
    printInfo("appending leftover image")
    # Append rest of file
    out.write(rgb)
    rgb = pic.read(1)
    while len(rgb) != 0:
        out.write(rgb)
        rgb = pic.read(1)


def checkSizeRequirements(picLength, secretLength, picOffset):
    if(picLength - picOffset < secretLength * (8 / bitlength)):
        printInfo("ERROR: picture too small to contain secret")
        printInfo("ERROR: aborting")
        sys.exit()
    return


########
# DECODE #
########


def decode():
    printInfo("")
    printInfo("DECODING MESSAGE START")
    printInfo("")
    try:
        # Verify bit length
        if bitlength == -1:
            printInfo("")
            printInfo("Error: Please specify bit length (eg. -b 4)")
            sys.exit()

        # Get pic size
        global picSize
        picSize = os.stat(picName).st_size

        # Get File handles
        global pic, out
        pic = open(picName, "rb")
        out = open(outName, "wb")

        # Find offset
        offset = getPixelArrayOffset()
        pic.seek(offset)

        # Read file length
        index = 0
        fileLengthBytes = ""
        while index < 4:
            unmasked = chr(0)
            byte = pic.read((8 / bitlength))
            i = 0
            for c in byte:
                for j in range(0, bitlength, 1):
                    unmasked = writeBit(unmasked, i, readBit(c, j))
                    i = i + 1
            fileLengthBytes = fileLengthBytes + unmasked
            index = index + 1

        fileLength = struct.unpack(">I", fileLengthBytes)[0]
        printInfo("secret length: {}".format(fileLength))

        # Get message from image
        index = 0
        while index < fileLength:
            unmasked = chr(0)
            byte = pic.read((8 / bitlength))
            i = 0
            for c in byte:
                for j in range(0, bitlength, 1):
                    unmasked = writeBit(unmasked, i, readBit(c, j))
                    i = i + 1
            out.write(unmasked)
            index = index + 1
    finally:
        pic.close()
        out.close()
        printInfo("")
        printInfo("DECODED MESSAGE")
        printInfo("")
    return


######
# UTILS #
######


def getPixelArrayOffset():
    # Skip to pointer to pixel array
    pic.read(10)
    # Read pixel array pointer
    offsetAsString = pic.read(4)
    offset = struct.unpack("<L", offsetAsString)[0]
    # Check if possible to hide file
    checkSizeRequirements(picSize, secretSize, offset)
    printInfo("pixel array starts at offset {}".format(offset))
    return offset


def readBit(byte, index):
    # return value of bit at index of byte
    return ord(byte) & (1 << index) != 0


def writeBit(byte, index, val):
    # write bit value to index of byte
    masked = ord(byte) & ~(1 << index)
    if val:
        masked |= (1 << index)
    return chr(masked)


def printInfo(info):
    print "\t {}".format(info)


def parseArgs(argv):
    global picName, secretName, outName, bitlength, mode
    try:
        opts, args = getopt.getopt(argv, "hp:s:o:b:", ["pfile=", "sfile=", "ofile=", "bits="])

        # Set some default options
        if "encode" in args:
            outName = "out.bmp"
        else:
            outName = "out.txt"
        bitlength = -1

        # Parse options
    except getopt.GetoptError:
        print 'steg.py -p <picfile> -s <secretfile> -o <outputfile> -b <nr of bits to abuse>'
        sys.exit(2)
    for opt, arg in opts:
        if opt == '-h':
            print 'steg.py -p <picfile> -s <secretfile> -o <outputfile> -b <nr of bits to abuse>'
            sys.exit()
        elif opt in ("-p", "--pfile"):
            picName = arg
        elif opt in ("-s", "--sfile"):
            secretName = arg
        elif opt in ("-o", "--ofile"):
            outName = arg
        elif opt in ("-b", "--bfile"):
            bitlength = int(arg)
            if bitlength not in (1, 2, 4, 8):
                printInfo("bit length must be 1, 2, 4 or 8")
                sys.exit()
    if "encode" in args:
        mode = "encode"
    elif "decode" in args:
        mode = "decode"
    else:
        printInfo("Please specify mode (encode/decode)")
        sys.exit()
    printInfo("Picture file is {}".format(picName))
    printInfo("Secret file is {}".format(secretName))
    printInfo("Output file is {}".format(outName))
    printInfo("Nr of abused bits per byte: {}".format(bitlength))
    return

if __name__ == "__main__":
    main(sys.argv[1:])
