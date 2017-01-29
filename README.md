# Simple-Steganography
A simple python script for embedding files of any type in bmp images. This is only a quick script. So it might contain bugs for unexpected input.
This script uses the n(can be specified) least significant bits in the color values of each pixel to encode the bits belonging to another file.

This allows you to hide files inside images without having a noticable visual impact on the image.
Depending on the amount of bits used per pixel the image will be more/less distorted. 

The ratio ImageSize/SecretFileSize determines the minimum amount of bits per pixel that have to be used to encode the secret file inside the image.
Obviously a secret file larger than the image file can never be encoded. If they are of equal size all pixels will be completely replaced by data of the secret file so it will be irrecognizable.


Usage and Command line options:
-----------------------------------------------
**Encode a secret file into a picture:**

    ./steg.py -p "input image.bmp" -s "secret file.???" -o "output file.bmp" -b bits_to_use_per_pixel_byte encode

- p: input image (bmp)
- s: secret file
- o: output image (bmp)
- b (optional): number of least significant bits to use from each byte of image (4 or lower recommended)
If the b parameter is not specified, the script will select the smallest amount that will fit.



**Decode a combined file into the secret file:**

    ./steg.py -p "combined.bmp" -o "output file.???" -b number_of_bits_used_to_encode decode

- p: input combined image (bmp)
- o: output secret file
- b: The value for b that was used to encode the image.
