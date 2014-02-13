import httplib, urllib

# TODO: This will eventually live in settings.py?
# probably put it as a database entry
PSHOVR_APP_TOKEN = "a3ACHSQN3nibApH7qNYFdNJsm2CfXV"
PSHOVR_USER_KEY = "n2hzjMkUjrg9xyBKsWaUxmQarf6bud"

def push_raw(title, message):
  conn = httplib.HTTPSConnection("api.pushover.net:443")
  conn.request("POST", "/1/messages.json",
    urllib.urlencode({
      "token": PSHOVR_APP_TOKEN,
      "user": PSHOVR_USER_KEY,
      "title": title,
      "message": message
    }), { "Content-type": "application/x-www-form-urlencoded" })

  resp = conn.getresponse()
  if resp.status != httplib.OK:
    # TODO: Push error to database.
    print "Pushover Error:"
    print "Status:", resp.status
    print "Reason:", resp.reason
    print "Message:", resp.msg

def push_failed_login(ipaddress, username, addendum=None):
  message = "Failed login attempt from "
  message += ipaddress
  message += " as "
  message += username
  if addendum:
    message += "; "+addendum
  push_raw("Failed Login", message)

def push_failed_totp(ipaddress, username):
  push_failed_login(ipaddress, username, "user provided invalid otp")

def push_improper_user(username, addendum=None):
  message = username
  message += " is not configured properly"
  if addendum:
    message += "; "+addendum
  push_raw("Invalid User Configuration", message)

