import cloudscraper
import garminconnect
import garth

print("Init garmin connect with cloudscraper on garth.client.sess...")
scraper = cloudscraper.create_scraper()
garth.client.sess = scraper
client = garminconnect.Garmin("rledward1@gmail.com", "Edwri0100")
try:
    client.login()
    print("Success")
except Exception as e:
    print("Failed with cloudscraper:", repr(e))
