from flask import Flask, render_template, request, session, redirect, url_for, send_file
import os
import uuid
import hashlib
import pymysql.cursors
from functools import wraps
import time

def loadFollowData(followRequests, people, username):
    # getPeopleQuery gets list of people you haven't sent follow request yet and yourself (so you can't try to follow self)
    getPeopleQuery = "SELECT * FROM person WHERE person.username NOT IN (SELECT followeeUsername FROM follow WHERE followerUsername = %s) " \
                     "AND person.username NOT IN (SELECT person.username FROM person WHERE person.username = %s)";
    getFollowRequestQuery = "SELECT * FROM follow WHERE follow.followeeUsername = %s AND acceptedFollow = 0"
    with connection.cursor() as cursor:
        cursor.execute(getFollowRequestQuery, (username))
    followRequests.extend(cursor.fetchall())
    with connection.cursor() as cursor:
        cursor.execute(getPeopleQuery, (username, username))
    people.extend(cursor.fetchall())

def loadFriendToGroupData(closefriendgroups, people, username):
    getGroupsQuery = "SELECT * FROM closefriendgroup WHERE groupOwner = %s"
    getPeopleQuery = "SELECT * FROM person"

    with connection.cursor() as cursor:
        cursor.execute(getGroupsQuery, (username))
    closefriendgroups.extend(cursor.fetchall())
    with connection.cursor() as cursor:
        cursor.execute(getPeopleQuery)
    people.extend(cursor.fetchall())

def loadTaggableData(tagData, photoID):
    getTaggableDataQuery = "SELECT * FROM tag WHERE tag.photoID NOT IN (SELECT photoID from tag WHERE tag.photoID = %s)"
    with connection.cursor() as cursor:
        cursor.execute(getTaggableDataQuery, (photoID))
    tagData.extend(cursor.fetchall())

def loadViewableImageData(imageData,username):
    getViewableImageDataQuery = "SELECT * FROM photo WHERE photoID IN(" \
                           "SELECT photoID FROM photo WHERE photoOwner=%s " \
                           "UNION " \
                           "SELECT photoID FROM share JOIN belong ON (share.groupName=belong.groupName AND share.groupOwner = belong.groupOwner) " \
                           "WHERE belong.username = %s " \
                           "UNION " \
                           "SELECT photoID FROM photo JOIN follow ON (photo.photoOwner = follow.followerUsername) " \
                           "WHERE photo.allFollowers = 1 AND follow.followerUsername = %s " \
                           "UNION " \
                           "SELECT photoID FROM tag WHERE tag.acceptedTag = 1 AND tag.username = %s)" \
                           "ORDER BY timestamp DESC"
    with connection.cursor() as cursor:
        cursor.execute(getViewableImageDataQuery, (username,username,username,username))
    imageData.extend(cursor.fetchall())

def loadTaggedImageData(imageData, username):
    getTaggedImageDataQuery = "SELECT * FROM photo WHERE photoID IN (SELECT photoID FROM tag WHERE acceptedTag = 0 AND username = %s)"
    with connection.cursor() as cursor:
        cursor.execute(getTaggedImageDataQuery, username)
    imageData.extend(cursor.fetchall())

def determineVisibility(userToCheck, photoID):
    visiblePhotoID, visiblePhotoIDNumbers = [], [] #first is dictionary, second is list
    getViewablePhotoIDQuery = "SELECT photoID FROM photo WHERE photoID IN(" \
                                "SELECT photoID FROM photo WHERE photoOwner=%s " \
                                "UNION " \
                                "SELECT photoID FROM share JOIN belong ON (share.groupName=belong.groupName AND share.groupOwner = belong.groupOwner) " \
                                "WHERE belong.username = %s " \
                                "UNION " \
                                "SELECT photoID FROM photo JOIN follow ON (photo.photoOwner = follow.followerUsername) " \
                                "WHERE photo.allFollowers = 1 AND follow.followerUsername = %s " \
                                "UNION " \
                                "SELECT photoID FROM tag WHERE tag.acceptedTag = 1 AND tag.username = %s)" \
                                "ORDER BY timestamp DESC"
    with connection.cursor() as cursor:
        cursor.execute(getViewablePhotoIDQuery, (userToCheck, userToCheck, userToCheck, userToCheck))
    visiblePhotoID = cursor.fetchall()
    print(visiblePhotoID)
    for dict in visiblePhotoID:
        visiblePhotoIDNumbers.append(dict["photoID"])
    photoID = int(photoID)
    if (photoID in visiblePhotoIDNumbers):
        return True
    return False

def loadSpecificImageData(photoID):
    loadSpecificImageQuery = "SELECT * FROM photo WHERE photoID = %s"
    with connection.cursor() as cursor:
        cursor.execute(loadSpecificImageQuery, photoID)
    return cursor.fetchone()

def loadTaggedUsersData(taggedUsers, photoID):

    loadTaggedUsersQuery = "SELECT username from tag WHERE photoID = %s AND acceptedTag = 1"
    with connection.cursor() as cursor:
        cursor.execute(loadTaggedUsersQuery, photoID)
    taggedUsers.extend(cursor.fetchall())

def loadTaggableUsersData(taggableUsers,photoID):

    loadTaggableUsersQuery = "SELECT username from person WHERE username NOT IN (SELECT username from tag WHERE photoID = %s)"
    with connection.cursor() as cursor:
        cursor.execute(loadTaggableUsersQuery, photoID)
    taggableUsers.extend(cursor.fetchall())
app = Flask(__name__)
app.secret_key = "super secret key"
IMAGES_DIR = os.path.join(os.getcwd(), "images")

connection = pymysql.connect(host="localhost",
                             database="finsta",
                             user="root",
                             password="",
                             cursorclass=pymysql.cursors.DictCursor,
                             autocommit=True)

def login_required(f):
    @wraps(f)
    def dec(*args, **kwargs):
        if not "username" in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return dec

@app.route("/")
def index():
    if "username" in session:
        return redirect(url_for("home"))
    return render_template("index.html")


@app.route("/home")
@login_required
def home():
    return render_template("home.html", username=session["username"])

@app.route("/tag/<photoID>", methods=['GET'])
@login_required
def tag(photoID):
    username = session["username"]
    taggedUsers, taggableUsers = [], []
    loadTaggedUsersData(taggedUsers,photoID)
    loadTaggableUsersData(taggableUsers, photoID)
    return render_template("tag.html", image=loadSpecificImageData(photoID), tagged=taggedUsers, taggable = taggableUsers, photoID = photoID)

@app.route("/tag/<photoID>", methods=['POST'])
@login_required
def tag2(photoID):
    username = session["username"]
    userToTag = request.form.get("taggableUsers")
    sendTagRequestQuery = "INSERT INTO tag VALUES (%s, %s, %s)"
    viewableImages, taggedUsers, taggableUsers  = [], [], []
    loadViewableImageData(viewableImages, userToTag)
    loadTaggedUsersData(taggedUsers, photoID)
    loadTaggableUsersData(taggableUsers, photoID)

    if (userToTag == username):
        with connection.cursor() as cursor:
            cursor.execute(sendTagRequestQuery, (username, photoID, 1))
        taggedUsers, taggableUsers = [], []
        loadTaggedUsersData(taggedUsers, photoID)
        loadTaggableUsersData(taggableUsers, photoID)
        message = "You have successfully tagged yourself in this photo!"
        return render_template("tag.html", image=loadSpecificImageData(photoID), tagged=taggedUsers, taggable=taggableUsers, message = message)
    else:
        try:
            if (determineVisibility(userToTag, photoID)): #if user can see photo
                sendTagRequestQuery = "INSERT INTO tag VALUES (%s, %s, %s)"
                with connection.cursor() as cursor:
                    cursor.execute(sendTagRequestQuery, (userToTag, photoID, 0))
                taggableUsers = [] #empty the data to reload
                loadTaggableUsersData(taggableUsers, photoID)
                message = "You have successfully sent a tag request to this user!"
                return render_template("tag.html", image=loadSpecificImageData(photoID), tagged=taggedUsers, taggable=taggableUsers, message = message)
            else: #if user cannot see photo
                taggableUsers = [] #empty the data to reload
                loadTaggableUsersData(taggableUsers, photoID)

                message = "This photo is not visible to that user!"
                return render_template("tag.html", image=loadSpecificImageData(photoID), tagged=taggedUsers, taggable=taggableUsers, message=message)
        except: #only necessary if showing people that have been sent request
            message = "This user has already been sent a tag request that is still pending!"
            return render_template("tag.html", image=loadSpecificImageData(photoID), tagged=taggedUsers, taggable=taggableUsers, message=message)
@app.route("/friendToGroup", methods=['GET','POST'])
@login_required
def friendToGroup():
    username = session["username"]
    closefriendgroups, people = [], []
    if request.method == 'GET':
        loadFriendToGroupData(closefriendgroups,people,username)
        return render_template("friendToGroup.html", closefriendgroups = closefriendgroups, people = people)

    if request.method == 'POST':
        closeFriendGroupSelected = request.form.get("closefriendgroups")
        personToAdd = request.form.get("people")
        insertUserQuery = "INSERT INTO belong VALUES (%s, %s, %s)"
        try:
            with connection.cursor() as cursor:
                cursor.execute(insertUserQuery, (closeFriendGroupSelected, username, personToAdd))
            message = "User successfully added"
            loadFriendToGroupData(closefriendgroups,people,username)
            return render_template("friendToGroup.html", message=message, closefriendgroups = closefriendgroups, people = people)
        except:
            message = "This person is already in that group"
            loadFriendToGroupData(closefriendgroups, people, username)
            return render_template("friendToGroup.html", message=message, closefriendgroups = closefriendgroups, people = people)



@app.route("/upload", methods=['GET'])
@login_required
def upload():
    username = session["username"]
    getGroupsQuery = "SELECT * FROM belong WHERE username = %s"
    with connection.cursor() as cursor:
        cursor.execute(getGroupsQuery, (username))
    closefriendgroups = cursor.fetchall()
    return render_template("upload.html", closefriendgroups = closefriendgroups)

@app.route("/follow", methods=['GET','POST'])
@login_required
def follow():
    username = session["username"]
    followRequests, people = [], []
    if request.method == 'GET':
        loadFollowData(followRequests, people, username)
        return render_template("follow.html", people = people, followRequests = followRequests)

    if request.method == 'POST':
        username = session["username"]
        if request.form['submit-button'] == "Accept":
            loadFollowData(followRequests, people, username)
            personToAccept = request.form.get("followRequestor")
            if (personToAccept == None):
                message = "You cannot leave both fields empty!"
                loadFollowData(followRequests, people, username)
                return render_template("follow.html", people=people, followRequests=followRequests, message=message)

            acceptUpdateQuery = "UPDATE follow SET acceptedfollow = 1 WHERE followerUsername = %s AND followeeUsername = %s"
            try:
                with connection.cursor() as cursor:
                    cursor.execute(acceptUpdateQuery, (personToAccept, username))
                message = "You have just accepted that user's follow request!"
                loadFollowData(followRequests, people, username)
                return render_template("follow.html", people=people, followRequests=followRequests, message=message)
            except:
                message = "You cannot leave both fields empty!"
                loadFollowData(followRequests, people, username)
                return render_template("follow.html", people=people, followRequests=followRequests, message=message)
        elif request.form['submit-button'] == "Reject":
            personToReject = request.form.get("followRequestor")
            if (personToReject == None):
                message = "You cannot leave both fields empty!"
                loadFollowData(followRequests, people, username)
                return render_template("follow.html", people=people, followRequests=followRequests, message=message)

            rejectUpdateQuery = "DELETE FROM follow WHERE followerUsername = %s AND followeeUsername = %s"
            try:
                with connection.cursor() as cursor:
                    cursor.execute(rejectUpdateQuery, (personToReject, username))
                message = "You have just rejected that user's follow request!"
                loadFollowData(followRequests, people, username)
                return render_template("follow.html", people=people, followRequests=followRequests, message=message)
            except:
                message = "You cannot leave both fields empty!"
                loadFollowData(followRequests, people, username)
                return render_template("follow.html", people=people, followRequests=followRequests, message=message)
        elif request.form['submit-button'] == "Send a Follow Request":
            personToFollow = request.form.get("personToFollow")
            sendFollowRequestQuery = "INSERT INTO follow VALUES (%s,%s,%s)"

            try:
                with connection.cursor() as cursor:
                    cursor.execute(sendFollowRequestQuery, (username, personToFollow, 0))
                message = "That user has just been sent a follow request!"
                loadFollowData(followRequests, people, username)
                return render_template("follow.html", people=people, followRequests=followRequests, message = message)
            except:
                message = "You cannot leave both fields empty!"
                loadFollowData(followRequests, people, username)
                return render_template("follow.html", people=people, followRequests=followRequests, message=message)

@app.route("/viewTags", methods=['GET'])
@login_required
def viewTagged():
    username = session["username"]
    imageData = []
    loadTaggedImageData(imageData, username)
    print(imageData)
    return render_template("viewTags.html", images=imageData)

@app.route("/viewTags", methods=['POST'])
@login_required
def viewTagged2():
    username = session["username"]
    imageData = []
    loadTaggedImageData(imageData, username)
    if request.form['submit-button-accept']: #if button pressed
        print(request.form['submit-button-accept'])
    else:
        print("brokes")
    return render_template("viewTags.html", images=imageData)
@app.route("/images", methods=["GET"])
@login_required
def images():
    username = session["username"]
    imageData = []
    loadViewableImageData(imageData, username)
    return render_template("images.html", images=imageData)

@app.route("/image/<image_name>", methods=["GET"])
def image(image_name):
    image_location = os.path.join(IMAGES_DIR, image_name)
    if os.path.isfile(image_location):
        return send_file(image_location, mimetype="image/jpg")

@app.route("/login", methods=["GET"])
def login():
    return render_template("login.html")

@app.route("/register", methods=["GET"])
def register():
    return render_template("register.html")

@app.route("/loginAuth", methods=["POST"])
def loginAuth():
    if request.form:
        requestData = request.form
        username = requestData["username"]
        plaintextPasword = requestData["password"]
        hashedPassword = hashlib.sha256(plaintextPasword.encode("utf-8")).hexdigest()

        with connection.cursor() as cursor:
            query = "SELECT * FROM person WHERE username = %s AND password = %s"
            cursor.execute(query, (username, hashedPassword))
        data = cursor.fetchone()
        if data:
            session["username"] = username
            return redirect(url_for("home"))

        error = "Incorrect username or password."
        return render_template("login.html", error=error)

    error = "An unknown error has occurred. Please try again."
    return render_template("login.html", error=error)

@app.route("/registerAuth", methods=["POST"])
def registerAuth():
    if request.form:
        requestData = request.form
        username = requestData["username"]
        plaintextPasword = requestData["password"]
        hashedPassword = hashlib.sha256(plaintextPasword.encode("utf-8")).hexdigest()
        firstName = requestData["fname"]
        lastName = requestData["lname"]

        try:
            with connection.cursor() as cursor:
                query = "INSERT INTO person (username, password, fname, lname) VALUES (%s, %s, %s, %s)"
                cursor.execute(query, (username, hashedPassword, firstName, lastName))
        except pymysql.err.IntegrityError:
            error = "%s is already taken." % (username)
            return render_template('register.html', error=error)

        return redirect(url_for("login"))

    error = "An error has occurred. Please try again."
    return render_template("register.html", error=error)

@app.route("/logout", methods=["GET"])
def logout():
    session.pop("username")
    return redirect("/")

@app.route("/uploadImage", methods=["POST"])
@login_required
def upload_image():
    if request.files:
        image_file = request.files.get("imageToUpload", "")
        image_name = image_file.filename
        filepath = os.path.join(IMAGES_DIR, image_name)
        image_file.save(filepath)
        username = session["username"]
        caption = request.form.get("caption")
        photoQuery = "INSERT INTO photo (photoOwner, timestamp, filePath, allFollowers, caption) VALUES (%s, %s, %s, %s, %s)"

        if request.form.get("allFollowers") == None:
            allFollowers_checked = False
        else:
            allFollowers_checked = True
        with connection.cursor() as cursor:
            cursor.execute(photoQuery, (username, time.strftime('%Y-%m-%d %H:%M:%S'), image_name, allFollowers_checked, caption))
            photoID = cursor.lastrowid
        message = "Image has been successfully uploaded."

        if request.form.get("allFollowers") == None:
            closeFriendGroupsSelected = request.form.getlist("closefriendgroups")
            for group in closeFriendGroupsSelected:
                with connection.cursor() as cursor:
                    getGroupInfoQuery = "SELECT * FROM closefriendgroup WHERE groupName LIKE %s"
                    cursor.execute(getGroupInfoQuery, (group))
                data = cursor.fetchone()
                print(data)
                shareQuery = "INSERT INTO share VALUES (%s, %s, %s)"
                with connection.cursor() as cursor:
                    cursor.execute(shareQuery, (data["groupName"],data["groupOwner"], photoID))

        return render_template("upload.html", message=message)
    else:
        message = "Failed to upload image."
        return render_template("upload.html", message=message)


if __name__ == "__main__":
    if not os.path.isdir("images"):
        os.mkdir(IMAGES_DIR)
    app.run(debug=True)