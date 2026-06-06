import sys

from Code.haiTaskList import haiTaskListScraper
from Code.haiCSVCreator import haiTaskListCSVCreator
from Code.haiExcelCreator import createHandshakeEarningsTracker

def getUserInputs():
    taskLink = "https://ai.joinhandshake.com/fellow/projects"

    print("Welcome to HAI Automatic Paycheck Calculator")
    print()

    startDateInput = input("Enter the start date. Only tasks and payments on or after this date will be included in the format MM/DD/YYYY: ").strip()
    endDateInput = input("Enter the end date. Only tasks and payments on or before this date will be included in the format MM/DD/YYYY: ").strip()

    outputFolder = input("Enter output folder name or press Enter to keep the default name \"OutputFolder\": ").strip()

    if not outputFolder:
        outputFolder = "OutputFolder"

    useAutomaticUcrLogin = False
    email = ""
    password = ""
    netid = ""

    ucrStudentInput = input("Are you a UCR student? Enter yes to use automatic UCR login, or press Enter for manual login (default: no): ").strip().lower()

    if ucrStudentInput in ["yes", "y"]:
        useAutomaticUcrLogin = True
        print("UCR auto-login requires your UCR Google email, UCR password, and UCR NetID.")
        print("If you leave any of these blank, the scraper will switch to manual login and wait 5 minutes so you can login manually.")

        email = input("Enter your UCR Google email: ").strip()
        password = input("Enter your UCR password: ").strip()
        netid = input("Enter your UCR NetID: ").strip()

        hasAllUcrCredentials = bool(email and password and netid)

        if not hasAllUcrCredentials:
            print()
            print("WARNING: You selected UCR auto-login, but email, password, or NetID was left blank.")
            print("Auto-login requires ALL 3 values: email, password, and NetID.")
            print("The scraper will switch to MANUAL LOGIN when Chrome opens.")
            print("You will have 5 minutes to login manually before the program closes.")
            print()
    else:
        print("WARNING: Manual login selected. Chrome will open and you will have 5 minutes to log in.")
        print("The scraper will continue once it sees the 'View project' button.")

    # Always close the browser when the scraper finishes.
    closeBrowserWhenDone = True

    createExcelInput = input(
        "Would you like the tool to automatically create or update the Handshake Earnings Tracker Excel file after scraping? Enter yes or no, or press Enter to use the default (yes): "
        ).strip().lower()
    createExcelTracker = createExcelInput not in ["no", "n"]

    existingExcelPath = None
    if createExcelTracker:
        existingExcelInput = input(
            "Enter existing Excel tracker file/folder path to update, or press Enter to create a new Excel Tracker File: "
        ).strip()

        if existingExcelInput:
            existingExcelPath = existingExcelInput

    return (
        taskLink,
        startDateInput,
        endDateInput,
        outputFolder,
        closeBrowserWhenDone,
        createExcelTracker,
        existingExcelPath,
        useAutomaticUcrLogin,
        email,
        password,
        netid,
    )


def main():
    try:
        (
            taskLink,
            startDateInput,
            endDateInput,
            outputFolder,
            closeBrowserWhenDone,
            createExcelTracker,
            existingExcelPath,
            useAutomaticUcrLogin,
            email,
            password,
            netid,
        ) = getUserInputs()

        # Run the Selenium task scraper first
        taskDateDict, handshakeWeeklySummaryData = haiTaskListScraper(
            link=taskLink,
            startDateInput=startDateInput,
            endDateInput=endDateInput,
            closeBrowserWhenDone=closeBrowserWhenDone,
            email=email,
            password=password,
            netid=netid,
            useAutomaticUcrLogin=useAutomaticUcrLogin,
        )

        if not taskDateDict:
            print("No CSV was created because the scraper did not return any task rows.")
            return

        # Run the CSV creator after the task scraper finishes
        csvFilePath = haiTaskListCSVCreator(taskDateDict, outputFolder=outputFolder)

        if csvFilePath:
            print(f"Toolchain finished successfully. CSV saved here: {csvFilePath}")
        else:
            print("The scraper finished, but the CSV file was not created.")
            return

        # Run the Excel creator using the CSV inside the same Output folder
        if createExcelTracker:
            excelFilePath = createHandshakeEarningsTracker(
                csvPath=csvFilePath,
                outputFolder=outputFolder,
                outputFileName="HandshakeEarningTracker.xlsx",
                existingWorkbookPath=existingExcelPath,
                handshakeWeeklySummaryData=handshakeWeeklySummaryData,
            )

            if excelFilePath:
                print(f"Toolchain finished successfully. Excel saved here: {excelFilePath}")
            else:
                print("CSV was created, but the Excel tracker was not created or updated.")
        else:
            print("Toolchain finished successfully. Excel creation was skipped.")

    except KeyboardInterrupt:
        print("Program stopped by user.")

    except Exception as error:
        print("Program failed because of an unexpected error.")
        print(f"Details: {error}")


if __name__ == "__main__":
    main()

    if getattr(sys, "frozen", False):
        try:
            input("\nPress Enter to exit...")
        except KeyboardInterrupt:
            pass
