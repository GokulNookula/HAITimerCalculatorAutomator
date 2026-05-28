from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
# import secret
import myThing #DELETE ME LATER once fully done coding

import csv # Make this part of code in a seperate python file
from datetime import datetime # Make this part of code in a seperate python file
import os # Make this part of code in a seperate python file


# Start Chrome and maximize window
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=(lambda o: (o.add_argument("--start-maximized"), o)[1])(Options()))

# Open the page
driver.get("https://ai.joinhandshake.com/fellow/15727563-a6cd-46b6-9c57-9bc1359b43b8/tasks")

# Wait for Google button and click it
googleButton = WebDriverWait(driver, 20).until(EC.element_to_be_clickable((By.XPATH, "//span[contains(text(),'Continue with Google')]")))
googleButton.click()

# Save original Handshake tab
mainWindow = driver.current_window_handle

# Wait for popup window
WebDriverWait(driver, 10).until(lambda d: len(d.window_handles) > 1)

for window in driver.window_handles:

    driver.switch_to.window(window)

    # Only continue if this is the Google sign in page
    if "accounts.google.com" in driver.current_url:

        # Inputting the email
        emailInput = WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.XPATH, '//*[@id="identifierId"]')))
        emailInput.send_keys(myThing.email)

        # Clicking next button
        nextButton = WebDriverWait(driver, 20).until(EC.element_to_be_clickable((By.XPATH, '//*[@id="identifierNext"]/div/button/span')))
        nextButton.click()

        # Wait for the username field to be present and enter the username
        usernameInput = WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.ID, "username")))
        usernameInput.send_keys(myThing.netid)

        # Locate and fill in the password field
        passwordInput = WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.ID, "password")))
        passwordInput.send_keys(myThing.password)

        # Locate and click the Sign In button
        signInButton = WebDriverWait(driver, 20).until(EC.element_to_be_clickable((By.XPATH, '//*[@id="fm1"]/div[2]/button')))
        signInButton.click()

        # Click "Yes this is my device" for UCR
        yesMyDeviceButton = WebDriverWait(driver, 60).until(EC.element_to_be_clickable((By.XPATH, '//*[@id="trust-browser-button"]')))
        yesMyDeviceButton.click()

        # Clicking Continue on Verify it's you page
        continueButton = WebDriverWait(driver, 60).until(EC.element_to_be_clickable((By.XPATH, '//*[@id="yDmH0d"]/div[1]/div[1]/div[2]/div/div/div[3]/div/div[1]/div/div/button')))
        continueButton.click()

        # Wait until popup closes
        WebDriverWait(driver, 60).until(lambda d: len(d.window_handles) == 1)

        # Switch back to main Handshake window
        driver.switch_to.window(mainWindow)

        break

# Wait for page element
headerText = WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.XPATH, "/html/body/div[2]/div[2]/main/main/div/div[1]/div[1]/div[1]/h1")))
# Get and print text
print(headerText.text)

# Getting the user's credential copy button
userEmailCpy = WebDriverWait(driver, 60).until(EC.presence_of_element_located((By.XPATH, '/html/body/div[2]/div[2]/main/main/div/div[1]/div[1]/div[2]/div[2]/div/div/p')))
print(userEmailCpy.text)

'''
Make this part of the code into a seperate part as a different file called dataSaver.py or something
'''
def parse_date(date_text):
    return datetime.strptime(date_text.strip(), "%m/%d/%Y").date()

# # User inputs pay-period range
# startDateInput = input("Enter start date MM/DD/YYYY: ")
# endDateInput = input("Enter end date MM/DD/YYYY: ")

# startDate = parse_date(startDateInput)
# endDate = parse_date(endDateInput)

startDate = parse_date("5/17/2026")
endDate = parse_date("5/27/2026")

# Create Output folder if it does not exist
outputFolder = "Output"

if not os.path.exists(outputFolder):
    os.makedirs(outputFolder)

# CSV file path
csvFilePath = os.path.join(outputFolder, "hhTaskFileList.csv")

# Wait for table rows to load
rows = WebDriverWait(driver, 30).until(
    EC.presence_of_all_elements_located((By.XPATH, "//table/tbody/tr"))
)

taskDateDict = []

# Now we need to iterate through the entire table to get the pay details
for row in rows:
    cells = row.find_elements(By.TAG_NAME, "td")

    if len(cells) >= 4:
        taskID = cells[0].text.strip().replace("\n", "")
        status = cells[1].text.strip()
        lastWorkedOn = cells[2].text.strip()
        totalTime = cells[3].text.strip()

        if lastWorkedOn:
            taskDate = parse_date(lastWorkedOn)

            if startDate <= taskDate <= endDate:
                taskDateDict.append({
                    "My Tasks": taskID,
                    "Status": status,
                    "Last worked on": lastWorkedOn,
                    "Total time": totalTime
                })

# Check if CSV already exists
fileExists = os.path.exists(csvFilePath)

# Write CSV
with open(csvFilePath, "w", newline="", encoding="utf-8") as file:

    writer = csv.DictWriter(file,fieldnames=["My Tasks", "Status", "Last worked on", "Total time"])

    writer.writeheader()
    writer.writerows(taskDateDict)

if fileExists:
    print(f"Updated existing CSV file: {csvFilePath}")
else:
    print(f"Created new CSV file: {csvFilePath}")

print(f"Saved {len(taskDateDict)} tasks.")

# Keep browser open for 30 seconds
time.sleep(400000)

# # Close browser
# driver.quit()