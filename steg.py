#!/usr/bin/python3.6

import struct
import os
import sys
import getopt
import math
from sty import fg, bg

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
    print_banner()
    parse_args(argv)
    update_settings_and_print()

    if mode == "encode":
        encode()
    elif mode == "decode":
        decode()

    return


def update_settings_and_print():
    global picSize, secretSize, bitlength
    picSize = int(os.stat(picName).st_size)

    if mode == "encode":
        secretSize = int(os.stat(secretName).st_size)
        if secretSize + 4 > picSize: # secret is appended with 4 bytes containing the secret length
            print_Error("There is insufficient room in the image file to store the secret")
            sys.exit()
        if(bitlength == -1):
            ratio = picSize / secretSize
            bitlength = math.ceil(8 / ratio)
            if bitlength == 0:
                bitlength = 1
            print_info("")
            print_info("Detected picture / secret ratio of {:.2f}. Using bit size of {}".format(ratio, bitlength))
            print_info("")

    print_info("Picture file is {}".format(picName))
    print_info("Secret file is {}".format(secretName))
    print_info("Output file is {}".format(outName))
    print_info("Nr of abused bits per byte: {}".format(bitlength))

##########
# ENCODE #
##########


def encode():
    global secretName, picSize, secretSize

    # Patch secret file with size data
    tmp = open(tmpFilePath, "wb")
    sizebytes = struct.pack(">I", secretSize)
    # printByte = "".join(["\\x%02X" % ord(c) for c in sizebytes])
    print_info("secret length: {}".format(secretSize))

    tmp.write(sizebytes)
    tmpSecretReader = open(secretName, "rb")
    tmpbyte = tmpSecretReader.read(1)
    while tmpbyte:
        tmp.write(tmpbyte)
        tmpbyte = tmpSecretReader.read(1)

    # Close patch reader and writer and reset secret name and size
    tmp.close()
    tmpSecretReader.close()
    secretName = tmpFilePath
    secretSize = os.stat(secretName).st_size

    # Open file handles
    global pic, secret, out
    pic = open(picName, "rb")
    secret = open(secretName, "rb")
    out = open(outName, "wb")

    patch_image()
    return


def patch_image():
    try:
        offset = get_pixel_array_offset()
        # Write header to out
        pic.seek(0)
        header = pic.read(offset)
        out.write(header)
        # Jump to pixel array
        pic.seek(offset)

        # encode each byte of the picture file untill we run out of secret file
        current_secret_bit_offset = 0
        (masked, current_secret_bit_offset) = encode_next_byte(pic, secret, current_secret_bit_offset)
        while current_secret_bit_offset != -1:
            out.write(masked.to_bytes(1, byteorder="little"))
            (masked, current_secret_bit_offset) = encode_next_byte(pic, secret, current_secret_bit_offset)

        # append rest of image file
        append_leftover_pic()
    finally:
        pic.close()
        secret.close()
        out.close()
        os.remove(tmpFilePath)
        print_info("COMPLETED STEGANOGRAPHY")
    return


def encode_next_byte(pic, secret, current_secret_bit_offset):
    byte_to_encode = secret.read(1)
    #print("secret: {}".format(byte_to_encode))

    if len(byte_to_encode) == 0:
        return (-1, -1)

    end_of_secret = False

    byte_to_encode_into = int.from_bytes(pic.read(1), byteorder="little")

    for i in range(0, bitlength, 1):
        secret_bit = read_bit(byte_to_encode, current_secret_bit_offset)
        byte_to_encode_into = write_bit(byte_to_encode_into, i, secret_bit)

        current_secret_bit_offset = current_secret_bit_offset + 1
        if current_secret_bit_offset % 8 == 0:
            current_secret_bit_offset = 0
            byte_to_encode = secret.read(1)
            if len(byte_to_encode) == 0:
                end_of_secret = True
                break

    if not end_of_secret:
        secret.seek(-1,1)
    #print("out: {}".format(byte_to_encode_into.to_bytes(1, byteorder="little")))

    return (byte_to_encode_into, current_secret_bit_offset)


def append_leftover_pic():
    print_info("appending leftover image")
    # Append rest of file
    rgb = pic.read(1)
    while len(rgb) != 0:
        out.write(rgb)
        rgb = pic.read(1)


def check_size_requirements(picLength, secretLength, picOffset):
    if(picLength - picOffset < secretLength * (8 / bitlength)):
        print_error("picture too small to contain secret")
        print_error("aborting")
        sys.exit()
    return


########
# DECODE #
########


def decode():
    print_info("")
    print_info("DECODING MESSAGE START")
    print_info("")
    try:
        # Get pic size
        global picSize
        picSize = os.stat(picName).st_size

        # Get File handles
        global pic, out
        pic = open(picName, "rb")
        out = open(outName, "wb")

        # Find offset
        offset = get_pixel_array_offset()
        pic.seek(offset)
        current_encoded_byte_offset = 0

        # Read file length
        index = 0
        fileLengthBytes = bytearray()
        while index < 4:
            unmasked = 0
            for i in range(0, 8):
                (decoded_bit, current_encoded_byte_offset) = read_next_bit(pic, current_encoded_byte_offset)
                unmasked = write_bit(unmasked, i, decoded_bit)
            fileLengthBytes.append(unmasked)
            index = index + 1

        fileLength = struct.unpack(">I", fileLengthBytes)[0]
        print_info("secret length: {}".format(fileLength))

        if fileLength * (8 / bitlength) > picSize:
            print_error("a secret size of {} is impossible in a file of size {} with a bit length of {}".format(fileLength, picSize, bitlength))
            sys.exit()

        # Get message from image
        index = 0
        while index < fileLength:
            unmasked = 0
            for i in range(0, 8):
                (decoded_bit, current_encoded_byte_offset) = read_next_bit(pic, current_encoded_byte_offset)
                if (decoded_bit == -1 and current_encoded_byte_offset == -1):
                    print_error("End of image file reached!")
                    print_error("Please make sure you are decoding an image with the correct bit length setting!")
                    print_error("Your current bitlength setting is {}".format(bitlength))
                    sys.exit()
                unmasked = write_bit(unmasked, i, decoded_bit)
            out.write(unmasked.to_bytes(1, byteorder="little"))
            index = index + 1

    finally:
        pic.close()
        out.close()
        print_info("")
        print_info("DECODED MESSAGE")
        print_info("")
    return


def read_next_bit(pic, current_encoded_byte_offset):
    encoded_byte = pic.read(1)
    if len(encoded_byte) == 0:
        return (-1, -1)
    decoded_bit = read_bit(encoded_byte, current_encoded_byte_offset)

    current_encoded_byte_offset = current_encoded_byte_offset + 1
    if current_encoded_byte_offset % bitlength == 0:
        current_encoded_byte_offset = 0;
    else:
        # There are still bits left in the current byte
        pic.seek(-1,1)

    return (decoded_bit, current_encoded_byte_offset)



######
# UTILS #
######


def get_pixel_array_offset():
    # Skip to pointer to pixel array
    pic.read(10)
    # Read pixel array pointer
    offsetAsString = pic.read(4)
    offset = struct.unpack("<L", offsetAsString)[0]
    # Check if possible to hide file
    check_size_requirements(picSize, secretSize, offset)
    print_info("pixel array starts at offset {}".format(offset))
    return offset


def read_bit(byte, index):
    # return value of bit at index of byte
    return ord(byte) & (1 << index) != 0


def write_bit(byte, index, val):
    # write bit value to index of byte
    masked = byte & ~(1 << index)
    if val:
        masked |= (1 << index)
    return masked


def print_info(info):
    print("{}".format(info))


def print_error(error):
    print(bg.red + "ERR:" + bg.rs + " {}".format(error))


def print_color(msg, color):
    print(color + "{}".format(msg) + bg.rs + fg.rs)


def parse_args(argv):
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
        print_help_and_exit()
    for opt, arg in opts:
        if opt == '-h':
            print_help_and_exit()
        elif opt in ("-p", "--pfile"):
            picName = arg
        elif opt in ("-s", "--sfile"):
            secretName = arg
        elif opt in ("-o", "--ofile"):
            outName = arg
        elif opt in ("-b", "--bfile"):
            bitlength = int(arg)
            if bitlength not in (1, 2, 3, 4, 5, 6, 7, 8):
                print_info("bit length must be 1, 2, 3, 4  5, 6, 7 or 8")
                sys.exit()
    if "encode" in args:
        mode = "encode"
    elif "decode" in args:
        mode = "decode"
    else:
        print_help_and_exit()

    # Verify bit length
    if mode == "decode" and bitlength == -1:
        print_info("")
        print_error("Decoding requires a bit length. Please specify bit length (eg. -b 4)")
        sys.exit()

    return


def print_banner():
    print_color("  _________.__               .__           _________ __                 ", fg.green)
    print_color(" /   _____/|__| _____ ______ |  |   ____  /   _____//  |_  ____   ____  ", fg.green)
    print_color(" \_____  \ |  |/     \\\\____ \|  | _/ __ \ \_____  \\\\   __\/ __ \ / ___\ ", fg.green)
    print_color(" /        \|  |  Y Y  \  |_> >  |_\  ___/ /        \|  | \  ___// /_/  >", fg.green)
    print_color("/_______  /|__|__|_|  /   __/|____/\___  >_______  /|__|  \___  >___  / ", fg.green)
    print_color("        \/          \/|__|             \/        \/           \/_____/  ", fg.green)
    print_color("                                                                        ", fg.green)
    print_color("   -> By Polle Vanhoof                                                  ", fg.green)
    print_color("                                                                        ", fg.green)


def print_help_and_exit():
    print_error("steg.py -p <picfile> -s <secretfile> -o <outputfile> -b <nr of bits to abuse> [encode|decode]")
    print_error("\t-p or --pfile > Filename of the picture to encode or decode")
    print_error("\t-s or --sfile > Filename of the secret that should be added to the image [only for encoding]")
    print_error("\t-o or --ofile > Filename for the output [default: out.bmp/out.txt]")
    print_error("\t-b or --bfile > Number of bits per byte to use [default: optimal spread]")
    sys.exit()


if __name__ == "__main__":
    main(sys.argv[1:])
