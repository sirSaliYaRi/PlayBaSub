from flask import Flask, render_template, request, url_for, redirect
import requests
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin, LoginManager, login_required, current_user, login_user, logout_user
import os


CLIENT_ID=os.getenv('CLIENT_ID')
CLIENT_SECRET=os.getenv('CLIENT_SECRET')
TOKEN_URL='https://id.twitch.tv/oauth2/token'
SUB_URL='https://api.twitch.tv/helix/subscriptions'
USERS_URL='https://api.twitch.tv/helix/users'
REDIRECT_URL='https://127.0.0.1:5000/twitchOAuth'

app= Flask(__name__)


app.config['SQLALCHEMY_DATABASE_URI']= "sqlite:///playbasub.db"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.getenv("SECRET_KEY")


lg= LoginManager(app)
@lg.user_loader
def load_user(user_id):
    return User.query.get(user_id)

db = SQLAlchemy(app)



class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    twitch_id = db.Column(db.Integer, unique=True, nullable=False)
    name = db.Column(db.String(50), nullable=False)
    access_token = db.Column(db.String(100), nullable=False)
    refresh_token = db.Column(db.String(100), nullable=False)
    subscribers = db.relationship("Subscriber", backref='channel')

class Subscriber(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    twitch_id = db.Column(db.Integer, unique=True, nullable=False)
    name = db.Column(db.String(50), nullable=False)
    channel_id = db.Column(db.Integer, db.ForeignKey('user.id'))

db.create_all()


@app.route('/')
def home():
    ### parameters used in a link's href that redirects user to twitch for authorisation
    params = "?response_type=code" \
             f"&client_id={CLIENT_ID}" \
             f"&redirect_uri={REDIRECT_URL}" \
             "&scope=channel%3Aread%3Asubscriptions+user%3Aread%3Aemail" \
             "&state=c3ab8aa609ea11e793ae92361f002671"

    return render_template('index.html', params=params)

@app.route('/twitchOAuth', methods=['GET'])
def authorise():
    ### a successful authorisation returns a json, that has a code key value pair, the code is used to get a token
    code = request.args['code']
    print(code)

    ### request a token with the 'code' in hand
    token_params= {
        'client_id':CLIENT_ID,
        'client_secret':CLIENT_SECRET,
        'code':code,
        'grant_type':'authorization_code',
        'redirect_uri': REDIRECT_URL,
    }
    response = requests.post(url=TOKEN_URL, data=token_params)
    tokens_data = response.json()
    access_token = tokens_data['access_token']
    refresh_token = tokens_data['refresh_token']
    print(tokens_data)


    ### get user's info
    users_header= {
        'Authorization': f'Bearer {access_token}',
        'Client-Id': CLIENT_ID,
    }
    response = requests.get(url=USERS_URL, headers=users_header)
    print(response.text)
    user_id = response.json()['data'][0]['id']
    user_name = response.json()['data'][0]['login']

    ## look if user already exists
    user_exists = False
    user = User.query.filter_by(twitch_id=user_id).first()
    if user:
        # user already exists
        user_exists = True
    else:
        user = User(
            twitch_id = user_id,
            name = user_name,
            access_token = access_token,
            refresh_token = refresh_token,
        )
        db.session.add(user)
        db.session.commit()


    ### get user's subscribers
    sub_header= {
        'Authorization': f'Bearer {access_token}',
        'Client-Id': CLIENT_ID,
    }
    sub_params= {
        'broadcaster_id': user_id,
    }
    response = requests.get(url=SUB_URL,params=sub_params,headers=sub_header)
    sub_data = response.json()
    print(sub_data)
    subscriptions = sub_data['data']

    if user_exists:
        subscribers = user.subscribers
        for subscriber in subscribers:
            db.session.delete(subscriber)
            db.session.commit()

    for subscription in subscriptions:
        subscriber = Subscriber (
            twitch_id = subscription['user_id'],
            name = subscription['user_loin'],
            channel_id = user.id,
        )
        db.session.add(subscriber)
        db.session.commit()


    return redirect('/')




@app.route('/dashboard')
@login_required
def dashboard():

    return render_template('dashboard.html')






if __name__ == "__main__":
    app.run(debug=True, ssl_context='adhoc')
