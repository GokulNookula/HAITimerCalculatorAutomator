from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import secret


# Start Chrome and maximize window
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=(lambda o: (o.add_argument("--start-maximized"), o)[1])(Options()))

# Open the page
driver.get("https://ai.joinhandshake.com/fellow/15727563-a6cd-46b6-9c57-9bc1359b43b8/tasks")

# Wait for Google button and click it
googleButton = WebDriverWait(driver, 20).until(EC.element_to_be_clickable((By.XPATH, "//span[contains(text(),'Continue with Google')]")))
googleButton.click()


# Keep browser open for 30 seconds
time.sleep(400000)

# # Close browser
# driver.quit()