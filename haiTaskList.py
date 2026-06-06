from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options

from selenium.common.exceptions import TimeoutException, WebDriverException, NoSuchWindowException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from datetime import datetime
import re
# import secret
import myThing #DELETE ME LATER once fully done coding


def parseDate(dateText: str):
    return datetime.strptime(dateText.strip(), "%m/%d/%Y").date()


def startChromeDriver():
    # Start Chrome and maximize window
    chromeOptions = Options()
    chromeOptions.add_argument("--start-maximized")

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chromeOptions)
    return driver


def waitForElement(driver, byType, locatorValue, timeoutSeconds, waitCondition, errorMessage):
    try:
        return WebDriverWait(driver, timeoutSeconds).until(waitCondition((byType, locatorValue)))
    except TimeoutException as error:
        raise RuntimeError(f"{errorMessage} Timed out after {timeoutSeconds} seconds. Locator used: {locatorValue}") from error


def extractProjectPayRate(payRateText: str):
    payRateMatch = re.search(r'\$\d+(?:\.\d+)?', payRateText)

    if not payRateMatch:
        raise ValueError(f"Could not find the project pay rate inside this text: {payRateText}")

    return payRateMatch.group()

def normalizeHandshakeProjectName(projectName: str):
    cleanedProjectName = projectName.strip()
    cleanedProjectName = cleanedProjectName.replace("–", "-").replace("—", "-")
    cleanedProjectName = re.sub(r"\s+", " ", cleanedProjectName)
    cleanedProjectName = re.sub(r"\s*-\s*", " - ", cleanedProjectName)

    return cleanedProjectName.strip().lower()


def getVisibleProjectNames(driver):
    projectNames = []

    projectCards = driver.find_elements(
        By.XPATH,
        "//section[.//button[normalize-space(.)='View project' or @aria-label='View project']]"
    )

    for projectCard in projectCards:
        projectNameElements = projectCard.find_elements(
            By.XPATH,
            ".//p[contains(@class,'rosetta-body-large')]"
        )

        if projectNameElements:
            projectName = projectNameElements[0].text.strip()

            if projectName:
                projectNames.append(projectName)

    return projectNames


def findProjectViewButton(driver, targetProjectName):
    normalizedTargetProjectName = normalizeHandshakeProjectName(targetProjectName)

    projectCards = driver.find_elements(
        By.XPATH,
        "//section[.//button[normalize-space(.)='View project' or @aria-label='View project']]"
    )

    for projectCard in projectCards:
        try:
            projectNameElements = projectCard.find_elements(
                By.XPATH,
                ".//p[contains(@class,'rosetta-body-large')]"
            )

            if not projectNameElements:
                continue

            displayedProjectName = projectNameElements[0].text.strip()
            normalizedDisplayedProjectName = normalizeHandshakeProjectName(displayedProjectName)

            if normalizedDisplayedProjectName != normalizedTargetProjectName:
                continue

            viewProjectButtons = projectCard.find_elements(
                By.XPATH,
                ".//button[normalize-space(.)='View project' or @aria-label='View project']"
            )

            if not viewProjectButtons:
                raise RuntimeError(
                    f"Found project '{displayedProjectName}', but could not find its View Project button."
                )

            return {
                "button": viewProjectButtons[0],
                "projectName": displayedProjectName
            }

        except WebDriverException:
            continue

    return False

def openHandshakeProjectByName(driver, targetProjectName="Project Hedgehog - Evals"):
    normalizedTargetProjectName = normalizeHandshakeProjectName(targetProjectName)

    waitForElement(
        driver,
        By.XPATH,
        "//main",
        120,
        EC.presence_of_element_located,
        "Could not find the Handshake AI main page after login."
    )

    try:
        projectMatch = WebDriverWait(driver, 120, poll_frequency=1).until(
            lambda d: findProjectViewButton(d, targetProjectName)
        )
    except TimeoutException as error:
        visibleProjectNames = getVisibleProjectNames(driver)
        raise RuntimeError(
            f"Could not find the exact project '{targetProjectName}'. "
            f"Projects found on the page: {visibleProjectNames}"
        ) from error

    viewProjectButton = projectMatch["button"]
    displayedProjectName = projectMatch["projectName"]

    driver.execute_script(
        "arguments[0].scrollIntoView({block: 'center', inline: 'nearest'});",
        viewProjectButton
    )

    oldUrl = driver.current_url

    try:
        WebDriverWait(driver, 20).until(
            lambda d: viewProjectButton.is_displayed() and viewProjectButton.is_enabled()
        )
        viewProjectButton.click()
    except WebDriverException:
        driver.execute_script("arguments[0].click();", viewProjectButton)

    # Wait until the page actually changes away from the AI Work projects page.
    try:
        WebDriverWait(driver, 60).until(lambda d: d.current_url != oldUrl)
    except TimeoutException:
        pass

    # Wait specifically for the real project page h1, not the old "AI work" h1.
    projectNameHeader = waitForElement(
        driver,
        By.XPATH,
        f"//h1[normalize-space()='{targetProjectName}']",
        120,
        EC.presence_of_element_located,
        f"Clicked View Project for '{displayedProjectName}', but the '{targetProjectName}' project page did not load."
    )

    if normalizeHandshakeProjectName(projectNameHeader.text) != normalizedTargetProjectName:
        raise RuntimeError(
            f"Clicked View Project for '{displayedProjectName}', but landed on "
            f"'{projectNameHeader.text}'. Expected '{targetProjectName}'."
        )

    print(f"Opened Handshake project: {projectNameHeader.text}")
    return projectNameHeader.text

def loginToHandshakeAI(driver):
    # Wait for Google button and click it
    googleButton = waitForElement(
        driver,
        By.XPATH,
        "//span[contains(text(),'Continue with Google')]",
        20,
        EC.element_to_be_clickable,
        "Could not find or click the 'Continue with Google' button."
    )
    googleButton.click()

    # Save original Handshake tab
    mainWindow = driver.current_window_handle

    # Wait for popup window
    try:
        WebDriverWait(driver, 10).until(lambda d: len(d.window_handles) > 1)
    except TimeoutException as error:
        raise RuntimeError("Google login popup did not open after clicking 'Continue with Google'.") from error

    googleWindowFound = False

    for window in driver.window_handles:

        driver.switch_to.window(window)

        # Only continue if this is the Google sign in page
        if "accounts.google.com" in driver.current_url:
            googleWindowFound = True

            # Inputting the email
            emailInput = waitForElement(
                driver,
                By.XPATH,
                '//*[@id="identifierId"]',
                20,
                EC.presence_of_element_located,
                "Could not find the Google email input."
            )
            emailInput.send_keys(myThing.email)

            # Clicking next button
            nextButton = waitForElement(
                driver,
                By.XPATH,
                '//*[@id="identifierNext"]/div/button/span',
                20,
                EC.element_to_be_clickable,
                "Could not find or click the Google email next button."
            )
            nextButton.click()

            # Wait for the username field to be present and enter the username
            usernameInput = waitForElement(
                driver,
                By.ID,
                "username",
                20,
                EC.presence_of_element_located,
                "Could not find the UCR username input."
            )
            usernameInput.send_keys(myThing.netid)

            # Locate and fill in the password field
            passwordInput = waitForElement(
                driver,
                By.ID,
                "password",
                20,
                EC.presence_of_element_located,
                "Could not find the UCR password input."
            )
            passwordInput.send_keys(myThing.password)

            # Locate and click the Sign In button
            signInButton = waitForElement(
                driver,
                By.XPATH,
                '//*[@id="fm1"]/div[2]/button',
                20,
                EC.element_to_be_clickable,
                "Could not find or click the UCR sign in button."
            )
            signInButton.click()

            # Click "Yes this is my device" for UCR
            yesMyDeviceButton = waitForElement(
                driver,
                By.XPATH,
                '//*[@id="trust-browser-button"]',
                60,
                EC.element_to_be_clickable,
                "Could not find or click the UCR 'Yes this is my device' button."
            )
            yesMyDeviceButton.click()

            # Clicking Continue on Verify it's you page
            continueButton = waitForElement(
                driver,
                By.XPATH,
                '//*[@id="yDmH0d"]/div[1]/div[1]/div[2]/div/div/div[3]/div/div[1]/div/div/button',
                60,
                EC.element_to_be_clickable,
                "Could not find or click the Google verify continue button."
            )
            continueButton.click()

            # Wait until popup closes
            try:
                WebDriverWait(driver, 60).until(lambda d: len(d.window_handles) == 1)
            except TimeoutException as error:
                raise RuntimeError("Google login popup did not close after finishing the login flow.") from error

            # Switch back to main Handshake window
            driver.switch_to.window(mainWindow)

            break

    if not googleWindowFound:
        raise RuntimeError("Could not find the Google sign in popup window.")


def scrapeTaskRows(driver, startDate, endDate, projName, projPayRate, userEmailCpy):
    # Wait for table rows to load
    rows = waitForElement(
        driver,
        By.XPATH,
        "//table/tbody/tr",
        30,
        EC.presence_of_all_elements_located,
        "Could not find the Handshake task table rows."
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
                try:
                    taskDate = parseDate(lastWorkedOn)
                except ValueError:
                    print(f"Skipping task {taskID}: could not parse date '{lastWorkedOn}'.")
                    continue

                if startDate <= taskDate <= endDate:
                    taskDateDict.append({
                        "My Tasks": taskID,
                        "Status": status,
                        "Last worked on": lastWorkedOn,
                        "Total time": totalTime,
                        "Project Name": projName,
                        "Project Pay Per Hour": projPayRate,
                        "HAI Email": userEmailCpy
                    })

    return taskDateDict


def haiTaskListScraper(link: str, startDateInput: str, endDateInput: str, closeBrowserWhenDone: bool = True):
    driver = None
    # EDIT ME ONCE YOU IMPLEMENT THIS
    handshakeWeeklySummaryData = None
    currentStep = "starting the scraper"

    try:
        startDate = parseDate(startDateInput)
        endDate = parseDate(endDateInput)

        if startDate > endDate:
            raise ValueError("The start date cannot be after the end date.")

        currentStep = "starting Chrome"
        driver = startChromeDriver()

        currentStep = "opening the Handshake AI task page"
        # Open the page
        driver.get(link)

        currentStep = "logging into Handshake AI with Google"
        loginToHandshakeAI(driver)

        currentStep = "opening the Hedgehog - Evals project"
        openHandshakeProjectByName(driver, "Project Hedgehog - Evals")

        currentStep = "getting the name of the project"
        # Getting the name of the project
        projNameElement = waitForElement(
            driver,
            By.XPATH,
            "/html/body/div[2]/div[2]/main/main/div/div[1]/div[1]/div[1]/h1",
            120,
            EC.presence_of_element_located,
            "Could not find the project name on the Handshake task page."
        )
        projName = projNameElement.text

        currentStep = "getting the pay of the project"
        # Getting the pay of the project
        projPayRateElement = waitForElement(
            driver,
            By.XPATH,
            "//p[contains(@class,'rosetta-body-medium') and contains(text(),'/hr')]",
            120,
            EC.presence_of_element_located,
            "Could not find the project pay rate on the Handshake task page."
        )
        projPayRate = extractProjectPayRate(projPayRateElement.text)
        print(f"Project pay rate found: {projPayRate}")

        currentStep = "getting the user's credential copy button"
        # Getting the user's credential copy button
        userEmailElement = waitForElement(
            driver,
            By.XPATH,
            '/html/body/div[2]/div[2]/main/main/div/div[1]/div[1]/div[2]/div[2]/div/div/p',
            60,
            EC.presence_of_element_located,
            "Could not find the HAI email/credential text on the Handshake task page."
        )
        userEmailCpy = userEmailElement.text

        currentStep = "scraping the task rows"
        taskDateDict = scrapeTaskRows(driver, startDate, endDate, projName, projPayRate, userEmailCpy)

        print(f"Found {len(taskDateDict)} tasks between {startDateInput} and {endDateInput}.")
        return taskDateDict, handshakeWeeklySummaryData

    except ValueError as error:
        print("Input error: please check your date range and input values.")
        print(f"Details: {error}")
        return None

    except RuntimeError as error:
        print("Selenium failed while running the Handshake AI scraper.")
        print(f"Step that failed: {currentStep}")
        print(f"Details: {error}")
        return None

    except NoSuchWindowException as error:
        print("Selenium failed because the browser window or login popup closed unexpectedly.")
        print(f"Step that failed: {currentStep}")
        print(f"Details: {error}")
        return None

    except WebDriverException as error:
        print("Selenium/WebDriver failed. This could be a ChromeDriver, Chrome, network, or browser automation issue.")
        print(f"Step that failed: {currentStep}")
        print(f"Details: {error}")
        return None

    except Exception as error:
        print("The scraper failed because of an unexpected error.")
        print(f"Step that failed: {currentStep}")
        print(f"Details: {error}")
        return None

    finally:
        if driver is not None and closeBrowserWhenDone:
            try:
                driver.quit()
            except Exception:
                pass


# Backwards compatible wrapper so old code using TaskScraper(...) still works
# This uses wide default dates only if you call the old function directly.
def TaskScraper(link: str):
    return haiTaskListScraper(link, "01/01/2000", "12/31/2100")
