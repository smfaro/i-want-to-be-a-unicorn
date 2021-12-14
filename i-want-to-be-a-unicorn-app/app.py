import json
import logging
import boto3
import botocore
import urllib
import os
import cv2

def lambda_handler(event, context):
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    logger.debug('event parameter: {}'.format(event))

    s3 = boto3.resource('s3')

    # Get the source image from the event
    source_bucket = event['Records'][0]['s3']['bucket']['name']
    source_key = urllib.parse.unquote_plus(event['Records'][0]['s3']['object']['key'], encoding='utf-8')
    tmp_filename='/tmp/original.jpg'
    try:
        s3.Bucket(source_bucket).download_file(source_key, tmp_filename)
    except botocore.exceptions.ClientError as e:
        if e.response['Error']['Code'] == "404":
            logger.error("The object does not exist: s3://" + source_bucket + source_key)
        else:
            raise

    # Create destination bucket if it doesnt exist
    aws_account_id = context.invoked_function_arn.split(":")[4]
    destination_bucket = 'i-want-to-be-a-unicorn-output-' + aws_account_id
    try:
        s3.create_bucket(Bucket=destination_bucket, CreateBucketConfiguration={'LocationConstraint': os.environ['AWS_REGION']})
    except botocore.exceptions.ClientError as e:
        logger.info("The output bucket already exists, moving on")

    # Get the haarcascade face data & unicorn horn img
    haarcascade_face_data_filename = os.environ['LAMBDA_TASK_ROOT'] + '/resources/haarcascade_frontalface_alt.xml'
    unicorn_horn_filename = os.environ['LAMBDA_TASK_ROOT'] + '/resources/unicorn.png'

    # Detect faces in source image
    img = cv2.imread(tmp_filename)
    faces = face_detect(img, haarcascade_face_data_filename)
    # Add overlay to each face
    for face in faces:
        unicorn_horn = cv2.imread(unicorn_horn_filename, -1)
        scale = face[3] / unicorn_horn.shape[0] * 2
        unicorn_horn = cv2.resize(unicorn_horn, (0, 0), fx=scale, fy=scale) 
        x_offset = int(face[0] + face[2] / 2 - unicorn_horn.shape[1] / 2) 
        y_offset = int(face[1] - unicorn_horn.shape[0] / 2) 
        x1 = max(x_offset, 0)
        x2 = min(x_offset + unicorn_horn.shape[1], img.shape[1])
        y1 = max(y_offset, 0)
        y2 = min(y_offset + unicorn_horn.shape[0], img.shape[0])
        unicorn_horn_x1 = max(0, -x_offset)
        unicorn_horn_x2 = unicorn_horn_x1 + x2 - x1
        unicorn_horn_y1 = max(0, -y_offset)
        unicorn_horn_y2 = unicorn_horn_y1 + y2 - y1
        alpha_h = unicorn_horn[unicorn_horn_y1:unicorn_horn_y2, unicorn_horn_x1:unicorn_horn_x2, 3] / 255
        alpha = 1 - alpha_h
        for c in range(3):
            img[y1:y2, x1:x2, c] = alpha_h * unicorn_horn[unicorn_horn_y1:unicorn_horn_y2, unicorn_horn_x1:unicorn_horn_x2, c] + alpha * img[y1:y2, x1:x2, c]
        cv2.imwrite(tmp_filename, img) 

    # Save the updated image to destination bucket
    s3 = boto3.client('s3')
    s3.upload_file(tmp_filename, destination_bucket, 'unicorn_' + source_key)

    return {
        "statusCode": 200,
        "body": json.dumps({
            "message": "image saved to s3://" + destination_bucket + "/unicorn_" + source_key,
        }),
    }

# Detect faces in image
def face_detect(img, cname):
    img_gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    img_hist = cv2.equalizeHist(img_gray)
    face_cascade = cv2.CascadeClassifier(cname)
    faces = face_cascade.detectMultiScale(img_hist)
    return faces
