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

def loginToHandshakeAI(driver, email, password, netid):
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
            # emailInput.send_keys(myThing.email)
            emailInput.send_keys(email)

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
            # usernameInput.send_keys(myThing.netid)
            usernameInput.send_keys(netid)

            # Locate and fill in the password field
            passwordInput = waitForElement(
                driver,
                By.ID,
                "password",
                20,
                EC.presence_of_element_located,
                "Could not find the UCR password input."
            )
            # passwordInput.send_keys(myThing.password)
            passwordInput.send_keys(password)

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
