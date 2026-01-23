import base64
import time
import pyotp


def main():
	s = ""
	token = base64.b32encode(bytes(s, "utf-8")).decode("utf-8")
	totp = pyotp.TOTP(token, digits=6, interval=60)
	r = totp.at(int(time.time() * 1000))
	print(s, ":", r)


if __name__ == '__main__':
	main()
