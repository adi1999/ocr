import pytesseract
import urllib
import cv2
import pyocr
#from StringIO import StringIO
import numpy as np
from PIL import Image
import io
import re
import difflib
import csv
import dateutil.parser as dparser
from PIL import Image
import matplotlib.pyplot as plt
# pytesseract.pytesseract.tesseract_cmd = r'C:\\Program Files\\Tesseract-OCR\\tesseract.exe'
import ftfy
import matplotlib.pyplot as plt
import os
import os.path
import json
import sys
import glob
import os
import random
import sys
import random
import math
import json
from collections import defaultdict
from PIL import Image, ImageDraw
import numpy as np
from scipy.ndimage.filters import rank_filter
from dateutil.parser import parse

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

    # orig_im = Image.open(path)
    orig_im = path
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

    text_im = orig_im.crop(crop)
    # text_im.show()
    return text_im

def empty():
    data = {}
    data['Name'] = 'Not found'
    data['Gender'] = 'Not found'
    data['Uid'] = 'Not found'
    data['Date of Birth'] = 'Not found'
    return data

class MyImage:
    def __init__(self, img_name):
        self.img = cv2.imread(img_name)
        self.__name = img_name

    def __str__(self):
        return self.__name

def process_image_aadhar_front(url=None,path=None):
    #image = _get_image(url)
    if url != None:
    	image = url_to_image(url)
    elif path != None:
    	image = MyImage(path)
    else:
    	return "Wrong Wrong Wrong, What are you doing ??? "

    im_pil = Image.fromarray(image.img)
    im_preprocessed = preprocess_image(im_pil)
    im_np = np.asarray(im_preprocessed)
    gray = cv2.cvtColor(im_np,cv2.COLOR_BGR2GRAY)


    # gray = cv2.cvtColor(image.img,cv2.COLOR_BGR2GRAY)
       #print ("Recognizing...")
    text=pytesseract.image_to_string(gray)

    name = None
    gender = None
    ayear = None
    uid = None
    yearline = []
    genline = []
    nameline = []
    text0 = []
    text1 = []
    text2 = []
    no = None
    lines=text
    text = text.replace("MOE","Male")

    text = text.replace("B:", "B: ")

    lines = text
    for wordlist in lines.split('\n'):
        xx = wordlist.split()
        if [w for w in xx if re.search('(Year|Birth|Year of Birth :|008:| 0B|> 0B |DOB;|> 0B :|00B:|YOB:|D0B:|DOB:|DOB|DO8:|DO8|D08:|DOR:)$', w)]:
            yearline = wordlist
            break
        else:
            text1.append(wordlist)
    try:
        text2 = text.split(yearline, 1)[1]
    except Exception:
        pass

    while("" in text1) :
        text1.remove("") 
    while(" " in text1) :
        text1.remove(" ") 
    while("  " in text1) : 
        text1.remove("  ") 
    while("   " in text1) : 
        text1.remove("   ") 
      
    if (len(text1)<1):
        name = "Not Found"
    else:   
        name=text1[len(text1)-1]
        name = name.replace('|', "")
        name = name.replace('©)', "")
        name = name.replace('-',"")
        name = name.replace("1",'')

    try:
        yearline = re.split('Year of Birth :| Year |Birth|Birth|of |008: |> 0B:|D0B: |0B :|Birth :|00B:|YoB|DOB :|DOB:|DOB|DO8:|DO8 |D08:|DOR:', yearline)[1:]
        yearline = ''.join(str(e) for e in yearline)
        if(yearline):
            ayear = dparser.parse(yearline,fuzzy=True).year
    except:
        pass

    if (len(yearline)==0):
        yearline = "Not Found"
    else:
        yearline = yearline.replace(":","")
        yearline = yearline.replace(";","")
        yearline = yearline.replace("i","")
        yearline = yearline.replace(" ","")
        yearline = yearline.replace("  ","")
        yearline = yearline.replace("ae","")

    lineno = 0  # to start from the first line of the text file.

    for wordline in text1:
        xx = wordline.split('\n')
        if ([w for w in xx if re.search('(Government of India|vernment of India|overnment of India|ernment of India|India|GOVT|GOVERNMENT|OVERNMENT|VERNMENT|GOVERNMENT OF INDIA|OVERNMENT OF INDIA|INDIA|NDIA)$', w)]):
            text1 = list(text1)
            lineno = text1.index(wordline)
            break
        
    text0 = text1[lineno+1:]
    try:
        for wordlist in lines.split('\n'):
            xx = wordlist.split( )
            if ([w for w in xx if re.search('(Female|Male|emale|male|ale|FEMALE|MALE|EMALE)$', w)]):
                genline = wordlist
                break
                
        if 'Male' in genline or 'MALE' in genline:
            gender = "Male"

        elif 'Female' in genline or 'FEMALE' in genline:
            gender = "Female"
        else:
            gender = "Not Found"

        text2 = text.split(genline,1)[1]

    except:
        pass

    text3= re.sub('\D', ' ', text2) #remove every character except numbers
    text3=text3.replace(" ","")
    text3=text3.replace("  ","")
    text3=text3.replace("   ","")
    text3=text3.replace("    ","")
    text3=text3.replace("     ","")
    text3[0:12]
    no=text3[0:12]
    no = no[0:4] + " " + no[4:8] +" " + no[8:12]

    name= re.sub(r'[^A-Za-z]', '', name)

    if(len(no) < 10):
        no = "Not Found"
    else:
        no = no

    if(len(name) < 3):
        name = "Not Found"
    else:
        name = name

    if(len(gender)<4):
        gender = "Not Found"
    else:
        gender = gender

    if(len(yearline)<3):
        yearline = "Not Found"
    else:
        yearline = yearline

    data = {}
    data['Name'] = name
    data['Gender'] = gender
    data['Date of Birth'] = yearline
    data['Uid']=no

    data['Name'] = re.sub('[\W_]+', ' ', data['Name'])
    data['Gender'] = re.sub('[\W_]+', ' ', data['Gender'])
    data['Uid'] = re.sub('[\W_]+', ' ', data['Uid'])

    try:
            to_unicode = unicode
    except NameError:
            to_unicode = str


    with io.open(str(image) + '_data' +'.json', 'w', encoding='utf-8') as outfile:
            str_ = json.dumps(data, indent=4, sort_keys=True, separators=(',', ': '), ensure_ascii=False)
            outfile.write(to_unicode(str_))



    print ("the result is {}".format(data))
    return data


def process_image_aadhar_back(url=None,path=None):
    #image = _get_image(url)
    if url != None:
        image = url_to_image(url)
    elif path != None:
        image = MyImage(path)
    else:
        return "Wrong Wrong Wrong, What are you doing ??? "


    im_pil = Image.fromarray(image.img)
    im_preprocessed = preprocess_image(im_pil)
    im_np = np.asarray(im_preprocessed)
    gray = cv2.cvtColor(im_np,cv2.COLOR_BGR2GRAY)

    # gray = cv2.cvtColor(image.img,cv2.COLOR_BGR2GRAY)
    text=pytesseract.image_to_string(gray)

    if text is None:
        data = empty()
        return data

    address = None
    state= None
    pincode = None
    district = None
    yearline = []
    genline = []
    nameline = []
    text0= []
    text1 = []
    text2 = []

    lines = text.split('\n')
    for lin in lines:
        s = lin.strip()
        s = lin.replace(' ','')
        s = lin.replace('\n','')
        s = s.rstrip()
        s = s.lstrip()
        text1.append(s)

    text1 = list(filter(None, text1))

    lineno = 0 # to start from the first line of the text file.

    for word in text1:
        xx = word.split()
        if ([w for w in xx if re.search('(Address: |Address:|Address:|dress:|ress:|dress|ress)$', w)]):
            address = word
            break
        else:
            text0.append(word)
    try:
        text2 = text.split(word, 1)[1]
    except Exception:
        pass

    keyword = 'Address'
    before_keyword, keyword, after_keyword = address.partition(keyword)

    Address_Line_1 = after_keyword
    Address_Line_1 = Address_Line_1.replace(":","")

    text2 = text2.replace("\n"," ")
    text2 = text2.replace("","")
    text2 = text2.replace("-",",")

    pincode = re.findall(r"\b(\d{6})\b", text2)


    def listToString(pc):  
        str1 = ""  
        for ele in pc:  
            str1 += ele   
        return str1 

    pincode = listToString(pincode)
    before_keyword2, keyword2, after_keyword2 = text2.partition(pincode)

    state = before_keyword2.rsplit(',', 2)[1]
    state = state.replace("   ","")
    state = state.replace("  ","")

    before_keyword5, keyword5, after_keyword5 = text2.partition(state)

    word_list = before_keyword5.split()

    district = word_list[len(word_list)-1]
    district = district.replace(",","")

    before_keyword3, keyword3, after_keyword3 = text2.partition(district)

    Address_Line_2 = before_keyword3

    Address = Address_Line_1 + Address_Line_2

    if(len(Address) < 4):
        Address = "Not Found"
    else:
        Address = Address

    if(len(state) < 4):
        state = "Not Found"
    else:
        state = state

    if(len(district) < 3):
        ditsrict = "Not Found"
    else:
        district = district

    if(len(pincode) < 6):
        pincode = "Not Found"
    else:
        pincode = pincode

    data={}
    #data['Address_Line_1']=Address_Line_1
    data['Address']=Address
    data['District'] = district
    data['State'] = state
    data['Pincode'] = pincode

    try:
            to_unicode = unicode
    except NameError:
            to_unicode = str

    with io.open(str(image) + '_data' +'.json', 'w', encoding='utf-8') as outfile:
            str_ = json.dumps(data, indent=4, sort_keys=True, separators=(',', ': '), ensure_ascii=False)
            outfile.write(to_unicode(str_))

    print ("the result is {}".format(data))
    return data


	
