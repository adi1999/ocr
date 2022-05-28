import pexpect
import os
from utils.classifier import Classifier
from config_pan import *
from typing import Tuple

class DarknetClassifier(Classifier):

	def initialize(self):
		''' Initialize darknet. We do this for speed concerns.
		Input:
			thresh (float)   - specifies the threshold of detection
			data (string)    - name of the data file for darknet
			cfg (string)     - name of the configuration file
			weights (string) - name of the pre-trained weights
		Return:
		   proc (pexpect process), which we use to interact with the running darknet process '''
		command = DARKNET_BINARY_LOCATION + " detector test " + DARKNET_DATA_FILE + " " + DARKNET_CFG_FILE \
			+ " " + DARKNET_WEIGHTS + " -thresh " + str(DARKNET_THRESH) + " -ext_output -dont_show"
		if os.name == 'nt':
			self.proc = popen_spawn.PopenSpawn(command)
		else:
			self.proc = pexpect.spawn(command)
		self.proc.expect('Enter Image Path:')

	def classify_image(self, image:str) -> str:
		''' Classifies a given image. Simply provide the name (string) of the image, and the proc to do it on.
		Input:
			image (string)   - name of the saved image file
			self.proc (proc)      - Pexpect proc to interact with
		Return:
			Returns the output from darknet, which gives the location of each bounding box. '''
		self.proc.sendline(image)
		self.proc.expect('Enter Image Path:', timeout=90)
		res = self.proc.before
		return res.decode('utf-8')
	def extract_info(self, line:str) -> Tuple:
		''' Extracts the information from a single line that contains a label.
		Input: line (string), a line that already contains the label
		Output: area (Tuple of four ints), which gives the area of the bounding box.
		'''
		nameplate_info = line.split()
		#print(nameplate_info)
		nameplate_confidence = nameplate_info[1]
		try:
			nameplate_left_x = int(nameplate_info[3])
		except:
			print('Can not convert', nameplate_info[3],"to int")
			nameplate_left_x = 1

		try:
			nameplate_top_y = int(nameplate_info[5])
		except:
			print('Can not convert', nameplate_info[5],"to int")
			nameplate_top_y = 1

		try:
			nameplate_width = int(nameplate_info[7])
		except:
			print('Can not convert', nameplate_info[7],"to int")
			nameplate_width = 1

		try:
			nameplate_height = int(nameplate_info[9][:-1])
		except:
			print('Can not convert', nameplate_info[9][:-1],"to int")
			nameplate_height = 1



		# nameplate_left_x = int(nameplate_info[3])
		# nameplate_top_y = int(nameplate_info[5])
		# nameplate_width = int(nameplate_info[7])
		# nameplate_height = int(nameplate_info[9][:-1])

		area = (nameplate_left_x, nameplate_top_y, (nameplate_left_x + nameplate_width), (nameplate_top_y + nameplate_height))

		return area
