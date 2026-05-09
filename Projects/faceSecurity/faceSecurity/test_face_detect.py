import face_recognition

image = face_recognition.load_image_file("owner_face.jpg")
encodings = face_recognition.face_encodings(image)
print("Number of faces found:", len(encodings))
