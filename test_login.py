import garminconnect
print("Init")
client = garminconnect.Garmin("rledward1@gmail.com", "Edwri0100")
print("Logging in...")
try:
    client.login()
    print("Success")
except Exception as e:
    print("Error:", repr(e))
