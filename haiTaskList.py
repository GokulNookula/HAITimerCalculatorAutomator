from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options

from selenium.common.exceptions import TimeoutException, WebDriverException, NoSuchWindowException, StaleElementReferenceException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from datetime import datetime
import re


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

def waitForManualLoginToProjectList(driver, targetProjectName="Project Hedgehog - Evals", timeoutSeconds=300):
    print(f"Manual login mode: please log in through the browser within {timeoutSeconds // 60} minutes.")
    print("Waiting until the project list loads and the 'View project' button is visible...")

    try:
        return WebDriverWait(driver, timeoutSeconds, poll_frequency=1).until(
            lambda d: findProjectViewButton(d, targetProjectName)
        )
    except TimeoutException as error:
        raise RuntimeError(
            f"Closed because the user did not login on time. "
            f"The scraper waited {timeoutSeconds // 60} minutes and never saw the 'View project' button."
        ) from error

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

def makeXPathLiteral(text: str):
    if "'" not in text:
        return f"'{text}'"

    if '"' not in text:
        return f'"{text}"'

    return "concat(" + ", \"'\", ".join(f"'{part}'" for part in text.split("'")) + ")"


def clickElementWithFallback(driver, element):
    driver.execute_script(
        "arguments[0].scrollIntoView({block: 'center', inline: 'nearest'});",
        element
    )

    try:
        element.click()
    except WebDriverException:
        driver.execute_script("arguments[0].click();", element)


def clickContinueWithGoogleButton(driver):
    googleButton = waitForElement(
        driver,
        By.XPATH,
        "//div[@role='button' and .//span[normalize-space(.)='Continue with Google']]"
        " | //button[.//span[normalize-space(.)='Continue with Google']]"
        " | //span[normalize-space(.)='Continue with Google']/ancestor::*[@role='button'][1]",
        20,
        EC.element_to_be_clickable,
        "Could not find or click the 'Continue with Google' button."
    )

    clickElementWithFallback(driver, googleButton)


def closeExtraGoogleLoginWindows(driver, mainWindow):
    for window in list(driver.window_handles):
        if window == mainWindow:
            continue

        try:
            driver.switch_to.window(window)
            driver.close()
        except WebDriverException:
            pass

    driver.switch_to.window(mainWindow)


def switchToGoogleLoginPopup(driver, mainWindow, timeoutSeconds=10):
    def findGooglePopup(currentDriver):
        for window in currentDriver.window_handles:
            if window == mainWindow:
                continue

            try:
                currentDriver.switch_to.window(window)

                if "accounts.google.com" in currentDriver.current_url:
                    return window

            except WebDriverException:
                continue

        return False

    try:
        return WebDriverWait(driver, timeoutSeconds, poll_frequency=1).until(findGooglePopup)
    except TimeoutException as error:
        raise RuntimeError("Google login popup did not open after clicking 'Continue with Google'.") from error


def waitForGoogleLoginPopupReady(driver, email, timeoutSeconds=6):
    emailXPathLiteral = makeXPathLiteral(email)

    savedAccountXPath = (
        f"//*[@data-email={emailXPathLiteral}]/ancestor::*[@role='link' or @role='button'][1]"
        f" | //*[normalize-space(.)={emailXPathLiteral}]/ancestor::*[@role='link' or @role='button'][1]"
    )

    def getGoogleLoginState(currentDriver):
        try:
            if len(currentDriver.window_handles) == 1:
                return "popupClosed"

            if currentDriver.find_elements(By.ID, "identifierId"):
                return "emailInput"

            if currentDriver.find_elements(By.XPATH, savedAccountXPath):
                return "savedAccountChooser"

            if currentDriver.find_elements(By.ID, "username") or currentDriver.find_elements(By.ID, "password"):
                return "ucrLogin"

            return False

        except (NoSuchWindowException, WebDriverException, StaleElementReferenceException):
            return False

    try:
        return WebDriverWait(driver, timeoutSeconds, poll_frequency=1).until(getGoogleLoginState)
    except TimeoutException as error:
        raise RuntimeError(
            "Google login popup opened, but it did not load the email input, saved account chooser, or UCR login page."
        ) from error


def clickSavedGoogleAccount(driver, email):
    emailXPathLiteral = makeXPathLiteral(email)

    savedAccountXPath = (
        f"//*[@data-email={emailXPathLiteral}]/ancestor::*[@role='link' or @role='button'][1]"
        f" | //*[normalize-space(.)={emailXPathLiteral}]/ancestor::*[@role='link' or @role='button'][1]"
    )

    savedAccountButton = waitForElement(
        driver,
        By.XPATH,
        savedAccountXPath,
        20,
        EC.element_to_be_clickable,
        f"Could not find or click the saved Google account for {email}."
    )

    clickElementWithFallback(driver, savedAccountButton)


def enterGoogleEmailAndContinue(driver, email):
    emailInput = waitForElement(
        driver,
        By.XPATH,
        '//*[@id="identifierId"]',
        20,
        EC.presence_of_element_located,
        "Could not find the Google email input."
    )

    emailInput.clear()
    emailInput.send_keys(email)

    nextButton = waitForElement(
        driver,
        By.XPATH,
        '//*[@id="identifierNext"]/div/button/span',
        20,
        EC.element_to_be_clickable,
        "Could not find or click the Google email next button."
    )

    clickElementWithFallback(driver, nextButton)


def optionalClickElement(driver, byType, locatorValue, timeoutSeconds):
    try:
        element = WebDriverWait(driver, timeoutSeconds).until(
            EC.element_to_be_clickable((byType, locatorValue))
        )
        clickElementWithFallback(driver, element)
        return True
    except TimeoutException:
        return False
    except WebDriverException:
        return False


def completeUcrLoginIfShown(driver, password, netid):
    try:
        usernameInput = WebDriverWait(driver, 20).until(
            lambda d: d.find_element(By.ID, "username")
            if d.find_elements(By.ID, "username")
            else False
        )
    except TimeoutException:
        return
    except (NoSuchWindowException, WebDriverException):
        return

    usernameInput.clear()
    usernameInput.send_keys(netid)

    passwordInput = waitForElement(
        driver,
        By.ID,
        "password",
        20,
        EC.presence_of_element_located,
        "Could not find the UCR password input."
    )

    passwordInput.clear()
    passwordInput.send_keys(password)

    signInButton = waitForElement(
        driver,
        By.XPATH,
        '//*[@id="fm1"]/div[2]/button',
        20,
        EC.element_to_be_clickable,
        "Could not find or click the UCR sign in button."
    )

    clickElementWithFallback(driver, signInButton)

    optionalClickElement(
        driver,
        By.XPATH,
        '//*[@id="trust-browser-button"]',
        60
    )

    optionalClickElement(
        driver,
        By.XPATH,
        '//*[@id="yDmH0d"]/div[1]/div[1]/div[2]/div/div/div[3]/div/div[1]/div/div/button',
        60
    )

def waitAfterGoogleAccountSelection(driver, mainWindow, timeoutSeconds=30):
    def getPostGoogleSelectionState(currentDriver):
        try:
            if len(currentDriver.window_handles) == 1:
                currentDriver.switch_to.window(mainWindow)
                return "popupClosed"

            for window in currentDriver.window_handles:
                if window == mainWindow:
                    continue

                try:
                    currentDriver.switch_to.window(window)

                    if currentDriver.find_elements(By.ID, "username") or currentDriver.find_elements(By.ID, "password"):
                        return "ucrLogin"

                except (NoSuchWindowException, WebDriverException):
                    continue

            return False

        except (NoSuchWindowException, WebDriverException, StaleElementReferenceException):
            return False

    try:
        return WebDriverWait(driver, timeoutSeconds, poll_frequency=1).until(getPostGoogleSelectionState)
    except TimeoutException as error:
        raise RuntimeError(
            "After selecting the Google account, the popup did not close and the UCR login page did not appear."
        ) from error

def loginToHandshakeAI(driver, email, password, netid):
    mainWindow = driver.current_window_handle
    maxLoginAttempts = 2
    lastError = None

    for attemptNumber in range(1, maxLoginAttempts + 1):
        try:
            print(f"Starting UCR Google auto-login attempt {attemptNumber} of {maxLoginAttempts}.")

            driver.switch_to.window(mainWindow)

            # Step 1: Click Continue with Google on the Handshake AI login page.
            clickContinueWithGoogleButton(driver)

            # Step 2: Switch into the Google popup.
            switchToGoogleLoginPopup(driver, mainWindow, timeoutSeconds=10)

            # Step 3: Wait for a usable Google page.
            # If the popup gets stuck on accounts.google.com/gsi/transform, this will timeout.
            googleLoginState = waitForGoogleLoginPopupReady(
                driver,
                email,
                timeoutSeconds=6
            )

            if googleLoginState == "popupClosed":
                driver.switch_to.window(mainWindow)
                print("Google popup closed. Continuing in the main Handshake AI window.")
                return

            if googleLoginState == "savedAccountChooser":
                print(f"Saved Google account found. Selecting {email}.")
                clickSavedGoogleAccount(driver, email)

                postGoogleSelectionState = waitAfterGoogleAccountSelection(
                    driver,
                    mainWindow,
                    timeoutSeconds=30
                )

                if postGoogleSelectionState == "popupClosed":
                    driver.switch_to.window(mainWindow)
                    print("Google account was accepted and the login popup closed.")
                    return

                if postGoogleSelectionState == "ucrLogin":
                    print("UCR login page found after selecting the saved Google account.")
                    completeUcrLoginIfShown(driver, password, netid)

            elif googleLoginState == "emailInput":
                print("Google email input found. Entering UCR email.")
                enterGoogleEmailAndContinue(driver, email)

                postGoogleSelectionState = waitAfterGoogleAccountSelection(
                    driver,
                    mainWindow,
                    timeoutSeconds=30
                )

                if postGoogleSelectionState == "popupClosed":
                    driver.switch_to.window(mainWindow)
                    print("Google account was accepted and the login popup closed.")
                    return

                if postGoogleSelectionState == "ucrLogin":
                    print("UCR login page found after entering the Google email.")
                    completeUcrLoginIfShown(driver, password, netid)

            elif googleLoginState == "ucrLogin":
                print("UCR login page found.")
                completeUcrLoginIfShown(driver, password, netid)

            # Step 4: Wait for the Google popup to close after UCR login finishes.
            try:
                WebDriverWait(driver, 45).until(lambda d: len(d.window_handles) == 1)
            except TimeoutException as error:
                raise RuntimeError("Google login popup did not close after finishing the login flow.") from error

            driver.switch_to.window(mainWindow)
            print("UCR Google auto-login finished successfully.")
            return

        except (RuntimeError, TimeoutException, WebDriverException, NoSuchWindowException) as error:
            lastError = error
            print(f"UCR Google auto-login attempt {attemptNumber} failed.")
            print(f"Details: {error}")

            try:
                closeExtraGoogleLoginWindows(driver, mainWindow)
            except WebDriverException:
                pass

            if attemptNumber < maxLoginAttempts:
                print("Retrying UCR Google login by clicking 'Continue with Google' again.")
            else:
                raise RuntimeError(
                    f"UCR Google auto-login failed after {maxLoginAttempts} attempts."
                ) from lastError

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

def getElementTextContent(driver, element):
    try:
        elementText = driver.execute_script("return arguments[0].textContent || '';", element)
        return re.sub(r"\s+", " ", elementText).strip()
    except StaleElementReferenceException:
        return ""


def normalizePaymentText(paymentText: str):
    cleanedPaymentText = paymentText.strip()
    cleanedPaymentText = cleanedPaymentText.replace("–", "-").replace("—", "-")
    cleanedPaymentText = re.sub(r"\s+", " ", cleanedPaymentText)
    cleanedPaymentText = re.sub(r"\s*-\s*", "-", cleanedPaymentText)

    return cleanedPaymentText.strip().lower()


def formatPaymentDateKey(paymentDate):
    return f"{paymentDate.month}/{paymentDate.day}/{paymentDate.year}"


def makePaymentWeekKey(weekStartDate, weekEndDate):
    return f"{formatPaymentDateKey(weekStartDate)} - {formatPaymentDateKey(weekEndDate)}"


def parsePaymentWeekDateRange(paymentWeekText: str):
    monthNameToNumber = {
        "jan": 1,
        "feb": 2,
        "mar": 3,
        "apr": 4,
        "may": 5,
        "jun": 6,
        "jul": 7,
        "aug": 8,
        "sep": 9,
        "oct": 10,
        "nov": 11,
        "dec": 12,
    }

    cleanedPaymentWeekText = paymentWeekText.strip()
    cleanedPaymentWeekText = cleanedPaymentWeekText.replace("–", "-").replace("—", "-")
    cleanedPaymentWeekText = re.sub(r"\s+", " ", cleanedPaymentWeekText)
    cleanedPaymentWeekText = re.sub(r",\s*Paid on.*$", "", cleanedPaymentWeekText, flags=re.IGNORECASE)

    dateRangeMatch = re.match(
        r"^(?P<startMonth>[A-Za-z]+)\s+"
        r"(?P<startDay>\d{1,2})\s*-\s*"
        r"(?:(?P<endMonth>[A-Za-z]+)\s+)?"
        r"(?P<endDay>\d{1,2}),\s*"
        r"(?P<endYear>\d{4})$",
        cleanedPaymentWeekText
    )

    if not dateRangeMatch:
        raise ValueError(f"Could not parse payment week date range: {paymentWeekText}")

    startMonthName = dateRangeMatch.group("startMonth")[:3].lower()
    endMonthName = dateRangeMatch.group("endMonth")
    endMonthName = endMonthName[:3].lower() if endMonthName else startMonthName

    if startMonthName not in monthNameToNumber or endMonthName not in monthNameToNumber:
        raise ValueError(f"Could not parse month name inside payment week date range: {paymentWeekText}")

    startMonthNumber = monthNameToNumber[startMonthName]
    endMonthNumber = monthNameToNumber[endMonthName]

    startDay = int(dateRangeMatch.group("startDay"))
    endDay = int(dateRangeMatch.group("endDay"))
    endYear = int(dateRangeMatch.group("endYear"))

    startYear = endYear

    # Handles ranges like Dec 29-Jan 4, 2026.
    if startMonthNumber > endMonthNumber:
        startYear = endYear - 1

    weekStartDate = datetime(startYear, startMonthNumber, startDay).date()
    weekEndDate = datetime(endYear, endMonthNumber, endDay).date()

    return weekStartDate, weekEndDate


def doesPaymentWeekOverlapDateRange(weekStartDate, weekEndDate, startDate, endDate):
    return weekStartDate <= endDate and weekEndDate >= startDate


def safeClickElement(driver, element):
    try:
        driver.execute_script(
            "arguments[0].scrollIntoView({block: 'center', inline: 'nearest'});",
            element
        )

        try:
            element.click()
        except WebDriverException:
            driver.execute_script("arguments[0].click();", element)

    except StaleElementReferenceException as error:
        raise RuntimeError("The element became stale before Selenium could click it.") from error


def findDropdownOptionByText(driver, optionText):
    try:
        dropdownOptions = driver.find_elements(By.XPATH, "//*[@role='option']")

        for dropdownOption in dropdownOptions:
            try:
                if not dropdownOption.is_displayed():
                    continue

                dropdownOptionText = getElementTextContent(driver, dropdownOption)

                if dropdownOptionText.strip().lower() == optionText.strip().lower():
                    return dropdownOption

            except StaleElementReferenceException:
                return False

    except StaleElementReferenceException:
        return False

    return False

def findPaymentTimeRangeDropdown(driver):
    validTimeRangeTexts = {
        "all time",
        "this week",
        "this month",
        "this quarter",
        "this year",
    }

    try:
        dropdownElements = driver.find_elements(By.XPATH, "//*[@role='combobox']")
        visibleDropdownElements = []

        for dropdownElement in dropdownElements:
            try:
                if not dropdownElement.is_displayed():
                    continue

                visibleDropdownElements.append(dropdownElement)

                dropdownTitle = (dropdownElement.get_attribute("title") or "").strip().lower()
                dropdownText = getElementTextContent(driver, dropdownElement).strip().lower()

                if dropdownTitle in validTimeRangeTexts or dropdownText in validTimeRangeTexts:
                    return dropdownElement

            except StaleElementReferenceException:
                return False

        # Fallback: on Payments page, second visible combobox is the date/time filter.
        if len(visibleDropdownElements) >= 2:
            return visibleDropdownElements[1]

    except StaleElementReferenceException:
        return False

    return False

def selectPaymentTimeRangeAllTime(driver):
    maxAttempts = 3
    lastError = None

    for attemptNumber in range(1, maxAttempts + 1):
        try:
            print(f"Selecting payment time range as All time. Attempt {attemptNumber} of {maxAttempts}.")

            timeRangeDropdown = WebDriverWait(driver, 60).until(
                lambda d: findPaymentTimeRangeDropdown(d)
            )

            currentDropdownText = getElementTextContent(driver, timeRangeDropdown).strip().lower()

            if currentDropdownText == "all time":
                WebDriverWait(driver, 60).until(lambda d: len(getPaymentWeekButtons(d)) > 0)
                return

            safeClickElement(driver, timeRangeDropdown)

            allTimeOption = WebDriverWait(driver, 30).until(
                lambda d: findDropdownOptionByText(d, "All time")
            )

            safeClickElement(driver, allTimeOption)

            # Do NOT reuse the old dropdown element after clicking All time.
            # The page re-renders, so re-find the dropdown fresh until it says All time.
            WebDriverWait(driver, 60).until(
                lambda d: getElementTextContent(d, findPaymentTimeRangeDropdown(d)).strip().lower() == "all time"
            )

            # Wait until the payment rows from the All time view exist after the re-render.
            WebDriverWait(driver, 60).until(
                lambda d: len(getPaymentWeekButtons(d)) > 0
            )

            return

        except (TimeoutException, WebDriverException, StaleElementReferenceException) as error:
            lastError = error
            print(f"Attempt {attemptNumber} failed while selecting All time.")

            if attemptNumber == maxAttempts:
                raise RuntimeError("Could not select the payment time range as All time after {maxAttempts} attempts.") from lastError

def extractPaymentWeekLabel(driver, paymentWeekButton):
    ariaLabel = paymentWeekButton.get_attribute("aria-label") or ""

    if ariaLabel:
        cleanedAriaLabel = re.sub(r",\s*Paid on.*$", "", ariaLabel, flags=re.IGNORECASE).strip()

        if cleanedAriaLabel:
            return cleanedAriaLabel

    buttonText = getElementTextContent(driver, paymentWeekButton)

    dateRangeMatch = re.search(
        r"[A-Za-z]+\s+\d{1,2}\s*[–—-]\s*(?:[A-Za-z]+\s+)?\d{1,2},\s*\d{4}",
        buttonText
    )

    if dateRangeMatch:
        return dateRangeMatch.group(0).strip()

    return ""


def getPaymentWeekButtons(driver):
    try:
        paymentWeekButtons = driver.find_elements(
            By.XPATH,
            "//button[contains(@aria-label, 'Paid on') or .//*[contains(normalize-space(.), 'Paid on')]]"
        )

        visiblePaymentWeekButtons = []

        for paymentWeekButton in paymentWeekButtons:
            try:
                if paymentWeekButton.is_displayed():
                    visiblePaymentWeekButtons.append(paymentWeekButton)
            except StaleElementReferenceException:
                return []

        return visiblePaymentWeekButtons

    except StaleElementReferenceException:
        return []


def findPaymentWeekButtonByLabel(driver, targetPaymentWeekLabel):
    normalizedTargetPaymentWeekLabel = normalizePaymentText(targetPaymentWeekLabel)

    for paymentWeekButton in getPaymentWeekButtons(driver):
        paymentWeekLabel = extractPaymentWeekLabel(driver, paymentWeekButton)

        if normalizePaymentText(paymentWeekLabel) == normalizedTargetPaymentWeekLabel:
            return paymentWeekButton

    return False


def getExpandedPaymentWeekDetailsContainer(paymentWeekButton):
    try:
        detailContainers = paymentWeekButton.find_elements(
            By.XPATH,
            "following-sibling::div[1]"
        )

        if not detailContainers:
            return None

        detailContainer = detailContainers[0]

        if detailContainer.is_displayed() and detailContainer.text.strip():
            return detailContainer

        return None

    except StaleElementReferenceException:
        return None


def findProjectPaymentRowInsideWeek(driver, detailContainer, projName):
    normalizedTargetProjectName = normalizeHandshakeProjectName(projName)

    projectNameSpans = detailContainer.find_elements(By.XPATH, ".//span")

    for projectNameSpan in projectNameSpans:
        projectNameText = getElementTextContent(driver, projectNameSpan)

        if normalizeHandshakeProjectName(projectNameText) != normalizedTargetProjectName:
            continue

        possibleRows = projectNameSpan.find_elements(
            By.XPATH,
            "./ancestor::div[contains(@class, 'grid')][1]"
        )

        if possibleRows:
            return possibleRows[0]

    return None

def convertHandshakeTimeToMinutes(handshakeTimeText: str):
    cleanedHandshakeTimeText = handshakeTimeText.strip()

    timeMatch = re.fullmatch(r"(?P<hours>\d+):(?P<minutes>\d{2})", cleanedHandshakeTimeText)

    if not timeMatch:
        raise ValueError(f"Could not convert Handshake time to minutes: {handshakeTimeText}")

    hours = int(timeMatch.group("hours"))
    minutes = int(timeMatch.group("minutes"))

    if minutes >= 60:
        raise ValueError(f"Invalid minutes value inside Handshake time: {handshakeTimeText}")

    return (hours * 60) + minutes

def extractProjectPaymentDataFromRow(driver, projectPaymentRow):
    rowSpans = projectPaymentRow.find_elements(By.XPATH, ".//span")
    rowTextValues = []

    for rowSpan in rowSpans:
        rowSpanText = getElementTextContent(driver, rowSpan)

        if rowSpanText:
            rowTextValues.append(rowSpanText)

    paidTimeText = None
    totalEarnings = None

    for rowTextValue in rowTextValues:
        if re.fullmatch(r"\d+:\d{2}", rowTextValue):
            paidTimeText = rowTextValue
            break

    for rowTextValue in reversed(rowTextValues):
        if re.fullmatch(r"\$[\d,]+(?:\.\d{2})?", rowTextValue):
            totalEarnings = rowTextValue
            break

    if not paidTimeText or not totalEarnings:
        raise RuntimeError(
            f"Could not extract paid time and total earnings from payment row: {rowTextValues}"
        )

    paidMinutes = convertHandshakeTimeToMinutes(paidTimeText)

    return paidMinutes, totalEarnings

def collectPaymentWeekInfos(driver):
    paymentWeekButtons = getPaymentWeekButtons(driver)

    if not paymentWeekButtons:
        return False

    paymentWeekInfos = []

    for paymentWeekButton in paymentWeekButtons:
        try:
            paymentWeekLabel = extractPaymentWeekLabel(driver, paymentWeekButton)

            if not paymentWeekLabel:
                continue

            weekStartDate, weekEndDate = parsePaymentWeekDateRange(paymentWeekLabel)

            paymentWeekInfos.append({
                "paymentWeekLabel": paymentWeekLabel,
                "weekStartDate": weekStartDate,
                "weekEndDate": weekEndDate
            })

        except StaleElementReferenceException:
            return False
        except ValueError as error:
            print(f"Skipping payment week because the date range could not be parsed.")
            print(f"Details: {error}")
            continue

    return paymentWeekInfos

def waitForProjectPaymentRowInsideWeek(driver, paymentWeekLabel, projName, timeoutSeconds=60):
    def findLoadedProjectRow(currentDriver):
        paymentWeekButton = findPaymentWeekButtonByLabel(currentDriver, paymentWeekLabel)

        if not paymentWeekButton:
            return False

        detailContainer = getExpandedPaymentWeekDetailsContainer(paymentWeekButton)

        if detailContainer is None:
            return False

        projectPaymentRow = findProjectPaymentRowInsideWeek(currentDriver, detailContainer, projName)

        if projectPaymentRow is None:
            return False

        return projectPaymentRow

    try:
        return WebDriverWait(driver, timeoutSeconds, poll_frequency=1).until(findLoadedProjectRow)
    except TimeoutException:
        return None

def paymentSectionScraper(driver, startDate, endDate, projName):
    handshakeWeeklySummaryData = {}

    paymentSectionButton = waitForElement(
        driver,
        By.XPATH,
        "//nav//a[normalize-space(.)='Payments']",
        60,
        EC.element_to_be_clickable,
        "Could not find the Payments link or was unable to open it."
    )
    safeClickElement(driver, paymentSectionButton)

    waitForElement(
        driver,
        By.XPATH,
        "//main",
        60,
        EC.presence_of_element_located,
        "The Payments page did not load correctly."
    )

    selectPaymentTimeRangeAllTime(driver)

    allPaymentWeekInfos = WebDriverWait(driver, 60).until(
        lambda d: collectPaymentWeekInfos(d)
    )

    paymentWeekInfos = []

    for paymentWeekInfo in allPaymentWeekInfos:
        weekStartDate = paymentWeekInfo["weekStartDate"]
        weekEndDate = paymentWeekInfo["weekEndDate"]

        if doesPaymentWeekOverlapDateRange(weekStartDate, weekEndDate, startDate, endDate):
            paymentWeekInfos.append(paymentWeekInfo)

    for paymentWeekInfo in paymentWeekInfos:
        paymentWeekLabel = paymentWeekInfo["paymentWeekLabel"]
        weekStartDate = paymentWeekInfo["weekStartDate"]
        weekEndDate = paymentWeekInfo["weekEndDate"]

        paymentWeekButton = WebDriverWait(driver, 30).until(
            lambda d: findPaymentWeekButtonByLabel(d, paymentWeekLabel)
        )

        detailContainer = getExpandedPaymentWeekDetailsContainer(paymentWeekButton)

        if detailContainer is None:
            safeClickElement(driver, paymentWeekButton)

            detailContainer = WebDriverWait(driver, 30).until(
                lambda d: getExpandedPaymentWeekDetailsContainer(
                    findPaymentWeekButtonByLabel(d, paymentWeekLabel)
                )
            )

        projectPaymentRow = waitForProjectPaymentRowInsideWeek(
            driver,
            paymentWeekLabel,
            projName,
            timeoutSeconds=60
        )

        if projectPaymentRow is None:
            print(f"Skipping {paymentWeekLabel}: no payment row found for {projName} after waiting 60 seconds.")
            continue

        paidMinutes, totalEarnings = extractProjectPaymentDataFromRow(driver, projectPaymentRow)

        paymentWeekKey = makePaymentWeekKey(weekStartDate, weekEndDate)

        handshakeWeeklySummaryData[paymentWeekKey] = {
            "paidMinutes": paidMinutes,
            "totalEarnings": totalEarnings,
            "projectName": projName,
        }

    print(f"Found {len(handshakeWeeklySummaryData)} payment weeks for {projName}.")
    return handshakeWeeklySummaryData

def haiTaskListScraper(link: str, startDateInput: str, 
                       endDateInput: str, 
                       closeBrowserWhenDone: bool = True,
                       email: str | None = None,
                       password: str | None = None,
                       netid: str | None = None,
                       useAutomaticUcrLogin: bool = False,
                       manualLoginTimeoutSeconds: int = 300):
    driver = None
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

        targetProjectName = "Project Hedgehog - Evals"

        if useAutomaticUcrLogin:
            email = (email or "").strip()
            password = (password or "").strip()
            netid = (netid or "").strip()

            hasAllUcrCredentials = bool(email and password and netid)

            if hasAllUcrCredentials:
                currentStep = "logging into Handshake AI with UCR Google auto-login"
                loginToHandshakeAI(driver, email, password, netid)
            else:
                print("UCR auto-login was selected, but email, password, or NetID was left blank.")
                print("Email, password, and NetID must ALL be provided for auto-login to work.")
                print("Switching to manual login now. Chrome will stay open for 5 minutes so you can log in.")

                currentStep = "waiting up to 5 minutes for manual login because UCR credentials were incomplete"
                waitForManualLoginToProjectList(
                    driver,
                    targetProjectName,
                    timeoutSeconds=manualLoginTimeoutSeconds
                )
        else:
            currentStep = "waiting up to 5 minutes for manual login"
            waitForManualLoginToProjectList(
                driver,
                targetProjectName,
                timeoutSeconds=manualLoginTimeoutSeconds
            )

        currentStep = "opening the Hedgehog - Evals project"
        openHandshakeProjectByName(driver, targetProjectName)

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

        currentStep = "scraping the payment weekly summary"
        handshakeWeeklySummaryData = paymentSectionScraper(driver, startDate, endDate, projName)

        print(f"Found {len(taskDateDict)} tasks between {startDateInput} and {endDateInput}.")
        return taskDateDict, handshakeWeeklySummaryData

    except ValueError as error:
        print("Input error: please check your date range and input values.")
        print(f"Details: {error}")
        return [], {}

    except RuntimeError as error:
        print("Selenium failed while running the Handshake AI scraper.")
        print(f"Step that failed: {currentStep}")
        print(f"Details: {error}")
        return [], {}

    except NoSuchWindowException as error:
        print("Selenium failed because the browser window or login popup closed unexpectedly.")
        print(f"Step that failed: {currentStep}")
        print(f"Details: {error}")
        return [], {}

    except WebDriverException as error:
        print("Selenium/WebDriver failed. This could be a ChromeDriver, Chrome, network, or browser automation issue.")
        print(f"Step that failed: {currentStep}")
        print(f"Details: {error}")
        return [], {}

    except Exception as error:
        print("The scraper failed because of an unexpected error.")
        print(f"Step that failed: {currentStep}")
        print(f"Details: {error}")
        return [], {}

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
