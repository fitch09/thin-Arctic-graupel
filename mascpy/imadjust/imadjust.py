#module pillow

from PIL import Image

def imadjust(img, lowerBound, upperBound):
	def adjust(p):
		if  p <= lowerBound*255: 
			p = 0
		elif p > upperBound*255: 
			p = 255
		else:
			p = ((p-lowerBound*255)/(upperBound-lowerBound))
		return p
	return img.point(adjust)

def im2bw(img, thresh):
	def binary(p):
		p = 0 if p <= thresh*255 else 255
		return p
	return img.point(binary)

originaIm  = Image.open('sample.png').convert("L")
adjustedIm = imadjust(originaIm, 0.05, 0.09)
binaryIm   = im2bw(adjustedIm, 0.5)

#originaIm.show()
#adjustedIm.show()
#binaryIm.show()
adjustedIm.save('adjusted.png')
binaryIm.save('binary.png')
