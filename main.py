# Modified from https://google.github.io/mediapipe/solutions/hands.html. 

from cgitb import handler
import cv2
import mediapipe as mp
import numpy as np
import pickle
import time

from sklearn.neural_network import MLPClassifier
from classifier import DataSaver

from inferencer import Hands, HAND_CONNECTIONS
from Touchpad import Touchpad
from Tracker import Tracker, TrackingSource
from classifier import GestureLabels

mp_drawing = mp.solutions.drawing_utils
mp_drawing_styles = mp.solutions.drawing_styles


def draw_palm_bbox(image, palm, color=(255, 0, 0)):

  palm_c = np.array([palm.x_center * image.shape[1], palm.y_center * image.shape[0]], dtype=int)
  
  halfX = palm.width / 2 * image.shape[1]
  halfY = palm.height / 2 * image.shape[0]
  R = np.array([
    [np.cos(-palm.rotation), -np.sin(-palm.rotation)],
    [np.sin(-palm.rotation), np.cos(-palm.rotation)]
  ])
  palm_ul = palm_c + (np.array([-halfX, -halfY]) @ R).astype(int)
  palm_ll = palm_c + (np.array([-halfX, halfY]) @ R).astype(int)
  palm_ur = palm_c + (np.array([halfX, -halfY]) @ R).astype(int)
  palm_lr = palm_c + (np.array([halfX, halfY]) @ R).astype(int)
  
  cv2.line(image, palm_ul, palm_ll, color=color)
  cv2.line(image, palm_ll, palm_lr, color=color)
  cv2.line(image, palm_lr, palm_ur, color=color)
  cv2.line(image, palm_ur, palm_ul, color=color)
  cv2.circle(image, palm_c, 5, color=color)




dataSaver = DataSaver()
keyToLabel = {
  ord('f'): GestureLabels.FIST,
  ord('l'): GestureLabels.LEFT_CLICK,
  ord('r'): GestureLabels.RIGHT_CLICK,
  ord('3'): GestureLabels.THREE,
  ord('4'): GestureLabels.FOUR,
  ord('5'): GestureLabels.FIVE,
  ord('p'): GestureLabels.PINCH,
}

with open('classifier/gesture_classifier.pickle', 'rb') as f:
  gesture_clf = pickle.load(f)


touchpad = Touchpad()
cap = cv2.VideoCapture(0)
if cap.isOpened():
  success, image = cap.read()
  tracker = Tracker(image_shape=image.shape[:2], trackWith=TrackingSource.HAND_LANDMARKS)

# For webcam input:
# static_image_mode allows palm bbox output, but lowers landmark quality as it no longer uses last landmark info. 
with Hands(
    use_custom_ssd=False, # Use True to use the custom 7-classes SSD model. 
    model_complexity=0,
    min_detection_confidence=0.5,
    max_num_hands=1,
    min_tracking_confidence=0.5) as hands:
  while cap.isOpened():
    success, image = cap.read()
    if not success:
      print("Ignoring empty camera frame.")
      # If loading a video, use 'break' instead of 'continue'.
      continue
    # image = cv2.imread("hand_icon.png")

    start_time = time.time()
    
    # To improve performance, optionally mark the image as not writeable to
    # pass by reference.
    image.flags.writeable = False
    image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    results = hands.process(image)

    # Draw the hand annotations on the image.
    image.flags.writeable = True
    image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
    if results.multi_hand_landmarks and results.hand_rects_from_palm_detections and results.hand_rects_from_landmarks:
      # Hand detected. 

      hand_landmarks = results.multi_hand_landmarks[0]
      palm_detection = results.hand_rects_from_palm_detections[0]
      palm_landmark = results.hand_rects_from_landmarks[0]

      # Draw hand landmarks. 
      mp_drawing.draw_landmarks(
          image,
          hand_landmarks,
          HAND_CONNECTIONS,
          mp_drawing_styles.get_default_hand_landmarks_style(),
          mp_drawing_styles.get_default_hand_connections_style())

      # Draw palm's bounding box. 
      draw_palm_bbox(image, palm_detection, color=(255, 0, 255))
      draw_palm_bbox(image, palm_landmark, color=(0, 255, 0))
      # print(results.palm_detections[0])

      # Detect gesture. 
      d = []
      for l in hand_landmarks.landmark:
        d.append(l.x)
        d.append(l.y)
        d.append(l.z)
      gesture = gesture_clf.predict([d])[0]
      print("gesture: " + str(gesture))

      # Track hand movement. 
      dDist = tracker.trackMovement(hand_landmarks, palm_landmark, gesture)

    else:
      # No hand, reset location averaging of the tracker. 
      dDist = np.array([0, 0], dtype = np.float64)
      gesture = GestureLabels.FIST
      tracker.reset()
      
    end_time = time.time()
    print(end_time - start_time)
    print()
      
    # Control mouse. 
    touchpad(gesture, dDist)

    # Flip the image horizontally for a selfie-view display.
    cv2.imshow('MediaPipe Hands', cv2.flip(image, 1))
    cv2.setWindowProperty('MediaPipe Hands', cv2.WND_PROP_TOPMOST, 1)

    pressed = cv2.waitKey(5)
    if pressed & 0xFF == 27:
      break
    elif pressed in keyToLabel.keys():
      dataSaver.addData(image, palm_detection, hand_landmarks, keyToLabel[pressed])

cap.release()