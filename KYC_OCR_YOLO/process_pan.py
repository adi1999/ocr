#!/bin/bash
from __future__ import print_function
from config_pan import *
from utils.darknet_classify_image import *
from utils.tesseract_ocr import *
import utils.logger as logger
import sys
from PIL import Image
import time
import os
import re
from operator import itemgetter
PYTHON_VERSION = sys.version_info[0]
OS_VERSION = os.name
import pandas as pd
import glob
import os
import random
import sys
import random
import math
import json
from collections import defaultdict
import re
import cv2
from PIL import Image, ImageDraw
import numpy as np
from scipy.ndimage.filters import rank_filter
from dateutil.parser import parse

class PanOCR():
	''' Finds and determines if given image contains required text and where it is. '''

	def init_vars(self):
		try:
			self.DARKNET = DARKNET
			
			self.TESSERACT = TESSERACT
			

			return 0
		except:
			return -1

	def init_classifier(self):
		''' Initializes the classifier '''
		try:
			if self.DARKNET:
			# Get a child process for speed considerations
				logger.good("Initializing Darknet")
				self.classifier = DarknetClassifier()
			
			if self.classifier == None or self.classifier == -1:
				return -1
			return 0
		except AssertionError as error:
			print(error)
			return -1

	def init_ocr(self):
		''' Initializes the OCR engine '''
		try:
			if self.TESSERACT:
				logger.good("Initializing Tesseract")
				self.OCR = TesseractOCR()
			
			if self.OCR == None or self.OCR == -1:
				return -1
			return 0
		except:
			return -1

	def init_tabComplete(self):
		''' Initializes the tab completer '''
		try:
			if OS_VERSION == "posix":
				global tabCompleter
				global readline
				from utils.PythonCompleter import tabCompleter
				import readline
				comp = tabCompleter()
				# we want to treat '/' as part of a word, so override the delimiters
				readline.set_completer_delims(' \t\n;')
				readline.parse_and_bind("tab: complete")
				readline.set_completer(comp.pathCompleter)
				if not comp:
					return -1
			return 0
		except:
			return -1

	def prompt_input(self):
		
		
			filename = str(input(" Specify File >>> "))
		

	from utils.locate_asset import locate_asset

	def initialize(self):
		if self.init_vars() != 0:
			logger.fatal("Init vars")
		if self.init_tabComplete() != 0:
			logger.fatal("Init tabcomplete")
		if self.init_classifier() != 0:
			logger.fatal("Init Classifier")
		if self.init_ocr() != 0:
			logger.fatal("Init OCR")
	

	def find_and_classify(self, filename):
		''' find the required text field from given image and read it through tesseract.
		    Results are stored in a dicionary. '''
		start = time.time()
		

		#------------------------------Classify Image----------------------------------------#

                
		logger.good("Classifying Image")
		
		coords = self.classifier.classify_image(filename)
		# print(coords)
		#lines=str(coords).split('\n')
		inf=[]
		for line in str(coords).split('\n'):
			if "Sign" in line:
				continue
			if "Photo" in line:
				continue
			if 'left_x' in line:
				info=line.split()
				# print(info[3])
				try:
					left_x = int(info[3])
				except:
					print('Can not convert', info[3] ,"to int")

				try:
					top_y = int(info[5])
				except:
					print('Can not convert', info[5] ,"to int")

				# top_y = int(info[5])
				# print()
				inf.append((info[0],left_x,top_y))
				# print(inf)
		

		time1 = time.time()
		print("Classify Time: " + str(time1-start))

		# ----------------------------Crop Image-------------------------------------------#
		logger.good("Finding required text")
		cropped_images = self.locate_asset(filename, self.classifier, lines=coords)
		
		
		time2 = time.time()
		

		
		#----------------------------Perform OCR-------------------------------------------#
		
		ocr_results = None
		
		if cropped_images == []:
			logger.bad("No text found!")
			return None 	 
		else:
			logger.good("Performing OCR")
			# ocr_results = self.OCR.ocr(cropped_images)   #original_line
			ocr_results_1 = self.OCR.ocr(cropped_images)
			ocr_results = [i for i in ocr_results_1 if len(i[1]) >1]




			# print(ocr_results[0])
			k=[]
			v=[]
			
			
			fil=filename+'-ocr'
			#with open(fil, 'w+') as f:
			for i in range(min(len(ocr_results), len(inf))):

							k.append(inf[i][0][:-1])
							v.append(ocr_results[i][1])
							print(ocr_results[i][1])
							
							print(inf[i][0][:-1])
							
			
			#v.insert(0,filename)
			# print(v)
			t=dict(zip(k, v))
			# print(t)
			

		
		time3 = time.time()
		print("OCR Time: " + str(time3-time2))

		end = time.time()
		logger.good("Elapsed: " + str(end-start))
		# print(t['Pan'])
		return t
		
		
			
		#----------------------------------------------------------------#

	def __init__(self):
		''' Run PanOCR '''
		self.initialize()





''' Image Preprocessing '''

def dilate(ary, N, iterations): 
    """Dilate using an NxN '+' sign shape. ary is np.uint8."""
    
    kernel = np.zeros((N,N), dtype=np.uint8)
    kernel[(N-1)//2,:] = 1  # Bug solved with // (integer division)
    
    dilated_image = cv2.dilate(ary / 255, kernel, iterations=iterations)
    
    kernel = np.zeros((N,N), dtype=np.uint8)
    kernel[:,(N-1)//2] = 1  # Bug solved with // (integer division)
    dilated_image = cv2.dilate(dilated_image, kernel, iterations=iterations)
    return dilated_image


def props_for_contours(contours, ary):
    """Calculate bounding box & the number of set pixels for each contour."""
    c_info = []
    for c in contours:
        x,y,w,h = cv2.boundingRect(c)
        c_im = np.zeros(ary.shape)
        cv2.drawContours(c_im, [c], 0, 255, -1)
        c_info.append({
            'x1': x,
            'y1': y,
            'x2': x + w - 1,
            'y2': y + h - 1,
            'sum': np.sum(ary * (c_im > 0))/255
        })
    return c_info


def union_crops(crop1, crop2):
    """Union two (x1, y1, x2, y2) rects."""
    x11, y11, x21, y21 = crop1
    x12, y12, x22, y22 = crop2
    return min(x11, x12), min(y11, y12), max(x21, x22), max(y21, y22)


def intersect_crops(crop1, crop2):
    x11, y11, x21, y21 = crop1
    x12, y12, x22, y22 = crop2
    return max(x11, x12), max(y11, y12), min(x21, x22), min(y21, y22)


def crop_area(crop):
    x1, y1, x2, y2 = crop
    return max(0, x2 - x1) * max(0, y2 - y1)


def find_border_components(contours, ary):
    borders = []
    area = ary.shape[0] * ary.shape[1]
    for i, c in enumerate(contours):
        x,y,w,h = cv2.boundingRect(c)
        if w * h > 0.5 * area:
            borders.append((i, x, y, x + w - 1, y + h - 1))
    return borders


def angle_from_right(deg):
    return min(deg % 90, 90 - (deg % 90))


def remove_border(contour, ary):
    """Remove everything outside a border contour."""
    # Use a rotated rectangle (should be a good approximation of a border).
    # If it's far from a right angle, it's probably two sides of a border and
    # we should use the bounding box instead.
    c_im = np.zeros(ary.shape)
    r = cv2.minAreaRect(contour)
    degs = r[2]
    if angle_from_right(degs) <= 10.0:
        box = cv2.boxPoints(r)
        box = np.int0(box)
        cv2.drawContours(c_im, [box], 0, 255, -1)
        cv2.drawContours(c_im, [box], 0, 0, 4)
    else:
        x1, y1, x2, y2 = cv2.boundingRect(contour)
        cv2.rectangle(c_im, (x1, y1), (x2, y2), 255, -1)
        cv2.rectangle(c_im, (x1, y1), (x2, y2), 0, 4)

    return np.minimum(c_im, ary)


def find_components(edges, max_components=16):
    """Dilate the image until there are just a few connected components.
    Returns contours for these components."""
    # Perform increasingly aggressive dilation until there are just a few
    # connected components.
    
    count = 21
    dilation = 5
    n = 1
    while count > 16:
        n += 1
        dilated_image = dilate(edges, N=3, iterations=n)
        dilated_image = np.uint8(dilated_image)
        contours, hierarchy = cv2.findContours(dilated_image, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
        count = len(contours)
    #print dilation
    #Image.fromarray(edges).show()
    #Image.fromarray(255 * dilated_image).show()
    return contours


def find_optimal_components_subset(contours, edges):
    """Find a crop which strikes a good balance of coverage/compactness.
    Returns an (x1, y1, x2, y2) tuple.
    """
    c_info = props_for_contours(contours, edges)
    c_info.sort(key=lambda x: -x['sum'])
    total = np.sum(edges) / 255
    area = edges.shape[0] * edges.shape[1]

    c = c_info[0]
    del c_info[0]
    this_crop = c['x1'], c['y1'], c['x2'], c['y2']
    crop = this_crop
    covered_sum = c['sum']

    while covered_sum < total:
        changed = False
        recall = 1.0 * covered_sum / total
        prec = 1 - 1.0 * crop_area(crop) / area
        f1 = 2 * (prec * recall / (prec + recall))
        #print '----'
        for i, c in enumerate(c_info):
            this_crop = c['x1'], c['y1'], c['x2'], c['y2']
            new_crop = union_crops(crop, this_crop)
            new_sum = covered_sum + c['sum']
            new_recall = 1.0 * new_sum / total
            new_prec = 1 - 1.0 * crop_area(new_crop) / area
            new_f1 = 2 * new_prec * new_recall / (new_prec + new_recall)

            # Add this crop if it improves f1 score,
            # _or_ it adds 25% of the remaining pixels for <15% crop expansion.
            # ^^^ very ad-hoc! make this smoother
            remaining_frac = c['sum'] / (total - covered_sum)
            new_area_frac = 1.0 * crop_area(new_crop) / crop_area(crop) - 1
            if new_f1 > f1 or (
                    remaining_frac > 0.25 and new_area_frac < 0.15):
                print('%d %s -> %s / %s (%s), %s -> %s / %s (%s), %s -> %s' % (
                        i, covered_sum, new_sum, total, remaining_frac,
                        crop_area(crop), crop_area(new_crop), area, new_area_frac,
                        f1, new_f1))
                crop = new_crop
                covered_sum = new_sum
                del c_info[i]
                changed = True
                break

        if not changed:
            break

    return crop


def pad_crop(crop, contours, edges, border_contour, pad_px=15):
    """Slightly expand the crop to get full contours.
    This will expand to include any contours it currently intersects, but will
    not expand past a border.
    """
    bx1, by1, bx2, by2 = 0, 0, edges.shape[0], edges.shape[1]
    if border_contour is not None and len(border_contour) > 0:
        c = props_for_contours([border_contour], edges)[0]
        bx1, by1, bx2, by2 = c['x1'] + 5, c['y1'] + 5, c['x2'] - 5, c['y2'] - 5

    def crop_in_border(crop):
        x1, y1, x2, y2 = crop
        x1 = max(x1 - pad_px, bx1)
        y1 = max(y1 - pad_px, by1)
        x2 = min(x2 + pad_px, bx2)
        y2 = min(y2 + pad_px, by2)
        return crop
    
    crop = crop_in_border(crop)

    c_info = props_for_contours(contours, edges)
    changed = False
    for c in c_info:
        this_crop = c['x1'], c['y1'], c['x2'], c['y2']
        this_area = crop_area(this_crop)
        int_area = crop_area(intersect_crops(crop, this_crop))
        new_crop = crop_in_border(union_crops(crop, this_crop))
        if 0 < int_area < this_area and crop != new_crop:
            print('%s -> %s' % (str(crop), str(new_crop)))
            changed = True
            crop = new_crop

    if changed:
        return pad_crop(crop, contours, edges, border_contour, pad_px)
    else:
        return crop


def downscale_image(im, max_dim=2048):
    """Shrink im until its longest dimension is <= max_dim.
    Returns new_image, scale (where scale <= 1).
    """
    a, b = im.size
    if max(a, b) <= max_dim:
        return 1.0, im

    scale = 1.0 * max_dim / max(a, b)
    new_im = im.resize((int(a * scale), int(b * scale)), Image.ANTIALIAS)
    return scale, new_im


def preprocess_image(path):

    orig_im = Image.open(path)
    scale, im = downscale_image(orig_im)

    edges = cv2.Canny(np.asarray(im), 100, 200)

    # TODO: dilate image _before_ finding a border. This is crazy sensitive!
    contours, hierarchy = cv2.findContours(edges, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    borders = find_border_components(contours, edges)
    borders.sort(key=lambda i_x1_y1_x2_y2: (i_x1_y1_x2_y2[3] - i_x1_y1_x2_y2[1]) * (i_x1_y1_x2_y2[4] - i_x1_y1_x2_y2[2]))

    border_contour = None
    if len(borders):
        border_contour = contours[borders[0][0]]
        edges = remove_border(border_contour, edges)

    edges = 255 * (edges > 0).astype(np.uint8)

    # Remove ~1px borders using a rank filter.
    maxed_rows = rank_filter(edges, -4, size=(1, 20))
    maxed_cols = rank_filter(edges, -4, size=(20, 1))
    debordered = np.minimum(np.minimum(edges, maxed_rows), maxed_cols)
    edges = debordered

    contours = find_components(edges)
    if len(contours) == 0:
        print('%s -> (no text!)' % path)
        return

    

    crop = find_optimal_components_subset(contours, edges)
    crop = pad_crop(crop, contours, edges, border_contour)

    crop = [int(x / scale) for x in crop]  # upscale to the original image size.
    #Start
    draw = ImageDraw.Draw(im)
    c_info = props_for_contours(contours, edges)
    for c in c_info:
        this_crop = c['x1'], c['y1'], c['x2'], c['y2']
        # draw.rectangle(this_crop, outline='blue')
    # draw.rectangle(crop, outline='red')
    # im.save(out_path)
    # draw.text((50, 50), path, fill='red')
    # orig_im.save(out_path)
    # im.show()
    #End
    text_im = orig_im.crop(crop)
    # text_im.show()
    return text_im
    # text_im.save(out_path)
    # print('%s -> %s' % (path, out_path))

extracter = PanOCR()
def process_image_pan(path=None):
		
		tim = time.time()
		
		data=[]


		image = preprocess_image(path)
		out_path = path
		image.save(out_path)

		result=extracter.find_and_classify(path)
		if result is None:
			result = {}
			result['Name'] = 'Not Found'
			result['FathersName'] = 'Not Found'
			result['Pan'] = 'Not Found'
			result['Date'] = 'Not Found'



        


		# print(result['Name'])
		if 'Name' in result :
			None	
		else:
			result['Name'] = 'Not Found'

		if 'FathersName' in result:
			None	
		else:
			result['FathersName'] = 'Not Found'

		if 'Pan' in result:
			None
				
		else:
			result['Pan'] = 'Not Found'
				

		if 'Date' in result:
			None
		else:
			result['Date'] = 'Not Found'
			#print(df1)
			#df=df.append(df1)

		result['Name'] = re.sub('[\W_]+', ' ', result['Name'])
		result['FathersName'] = re.sub('[\W_]+', ' ', result['FathersName'])
		result['Pan'] = re.sub('[\W_]+', ' ', result['Pan'])



		def remove_garbage_from_Date(test_string):
			bad_chars = [';', ':', '!', "*", '@', '$', '%', '^', '&']
			for i in bad_chars :
				test_string = test_string.replace(i, '')
			return test_string


		def is_date(string, fuzzy=False):
			try:
				parse(string, fuzzy=fuzzy)
				return True
			except ValueError:
				return False


		print(result['Date'])


		result['Date'] = remove_garbage_from_Date(result['Date'])

		if(is_date(result['Date'])):
			print('Found DOB')
		else:
			result['DOB'] = 'Not Found'




		print(result['Name'])
		print(result['FathersName'])
		print(result['Pan'])

		print(result['Date'])

		def isValid(Z):
			Result=re.compile("[A-Za-z]{5}\d{4}[A-Za-z]{1}")
			return Result.match(Z)

		if (isValid(result['Pan'])):
			print('Found Pan')
		elif(isValid(result['Date'])):
			result['Pan'] = result['Date']
		elif(isValid(result['FathersName'])):
			result['Pan'] = result['FathersName']

		else:
			result['Pan'] = 'Not Found'

		if all(x.isalpha() or x.isspace() for x in result['FathersName']):
			print('Found FathersName')
		else:
			result['FathersName'] = 'Not Found'

		if all(x.isalpha() or x.isspace() for x in result['Name']):
			print('Found Name')
		else:
			result['Name'] = 'Not Found'

		if(is_date(result['Date'])):
			print('Found DOB')
		else:
			result['DOB'] = 'Not Found'



		
		data.append(result)
		
		df=pd.DataFrame(data)
		#print(df)
		df.to_csv (r'output/ocr_result_pan.csv', index = None, header=True,sep='\t')
		en = time.time()
		print('TOTAL TIME TAKEN',str(en-tim))
		return result
