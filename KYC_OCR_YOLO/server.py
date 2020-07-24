from flask import Flask
import os
import logging
from logging import Formatter, FileHandler
from flask import Flask, request, jsonify, render_template,redirect,make_response,url_for
from werkzeug.utils import secure_filename
from process_pan import process_image_pan
from pre_img_aadhar import process_image_aadhar_front
from pre_img_aadhar import process_image_aadhar_back
# from d_aadhar.process_aadhar import process_image_aadhar_front
basedir = os.path.abspath(os.path.dirname(__file__))

UPLOAD_FOLDER = './pancards'
ALLOWED_EXTENSIONS = set(['png', 'jpg', 'jpeg', 'gif', 'jfif'])

app = Flask(__name__)
app.config['JSON_SORT_KEYS'] = False
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

_VERSION = 1  # API version

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/upload',methods=['POST'])
# @app.route('/upload',methods=['GET','POST'])
def upload_file():
    if request.method == 'POST':
        Key = request.form.get("Key")

        if Key == 'Pan':
            file = request.files['file']

            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                path="./pancards/{}".format(filename)
                print ("file was uploaded in {} ".format(path))
                rec_string = process_image_pan(path=path)
                return jsonify({"Name" : rec_string['Name'], "Father Name" : rec_string['FathersName'], "DOB" : rec_string['Date'], "PAN" : rec_string['Pan'] }  )


        elif Key == 'Aadhar':
            front = request.files['front']
            back = request.files['back']
            if front and allowed_file(front.filename):
                filename = secure_filename(front.filename)
                front.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                path="./pancards/{}".format(filename)
                print ("file was uploaded in {} ".format(path))
                rec_string1 = process_image_aadhar_front(path=path)
                filename = secure_filename(back.filename)
                back.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                path="./pancards/{}".format(filename)
                print ("file was uploaded in {} ".format(path))
                rec_string2 = process_image_aadhar_back(path=path)
                return jsonify({ "Name" : rec_string1['Name'], "DOB" : rec_string1['Date of Birth'], "Gender" : rec_string1['Gender'] , "Uid" : rec_string1['Uid'], "Address" : rec_string2['Address'], "District" : rec_string2['District'], "State" : rec_string2['State'], "Pincode" : rec_string2['Pincode']})




@app.errorhandler(500)
def internal_error(error):
    print(str(error))  # ghetto logging

@app.errorhandler(404)
def not_found_error(error):
    print(str(error))

@app.errorhandler(405)
def not_allowed_error(error):
    print(str(error))

if not app.debug:
    file_handler = FileHandler('error.log')
    file_handler.setFormatter(
        Formatter('%(asctime)s %(levelname)s: \
            %(message)s [in %(pathname)s:%(lineno)d]')
    )
    app.logger.setLevel(logging.INFO)
    file_handler.setLevel(logging.INFO)
    app.logger.addHandler(file_handler)
    app.logger.info('errors')

if __name__ == '__main__':
    #app.debug = True
    app.run(host="127.0.0.1",port = int(8080))
