import os
import shutil
import glob


def main():
    base = "/mnt/webcam/html/camchive/hik/2018"
    for suffix in ["05", "25", "35", "55"]:
        for f in glob.iglob(base + "/**/**", recursive=True):
            if f.endswith(suffix + "hik.jpg"):
                print(f)
                os.remove(f)


if __name__ == "__main__":
    main()
