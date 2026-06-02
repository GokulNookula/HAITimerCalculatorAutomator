from haiTaskList import haiTaskListScraper
from haiCSVCreator import haiTaskListCSVCreator


def getUserInputs():
    defaultTaskLink = "https://ai.joinhandshake.com/fellow/15727563-a6cd-46b6-9c57-9bc1359b43b8/tasks"

    print("Handshake AI Task List CSV Tool")
    print("Leave the task link blank to use the default Project Hedgehog task link.")

    taskLink = input("Enter Handshake AI task link: ").strip()

    if not taskLink:
        taskLink = defaultTaskLink

    startDateInput = input("Enter start date MM/DD/YYYY: ").strip()
    endDateInput = input("Enter end date MM/DD/YYYY: ").strip()

    outputFolder = input("Enter output folder name or press Enter for Output: ").strip()

    if not outputFolder:
        outputFolder = "Output"

    keepBrowserOpenInput = input("Keep browser open after scraping? yes/no, default no: ").strip().lower()
    closeBrowserWhenDone = keepBrowserOpenInput not in ["yes", "y"]

    return taskLink, startDateInput, endDateInput, outputFolder, closeBrowserWhenDone


def main():
    try:
        taskLink, startDateInput, endDateInput, outputFolder, closeBrowserWhenDone = getUserInputs()

        # Run the Selenium task scraper first
        taskDateDict = haiTaskListScraper(taskLink, startDateInput, endDateInput, closeBrowserWhenDone)

        if not taskDateDict:
            print("No CSV was created because the scraper did not return any task rows.")
            return

        # Run the CSV creator after the task scraper finishes
        csvFilePath = haiTaskListCSVCreator(taskDateDict, outputFolder=outputFolder)

        if csvFilePath:
            print(f"Toolchain finished successfully. CSV saved here: {csvFilePath}")
        else:
            print("The scraper finished, but the CSV file was not created.")

    except KeyboardInterrupt:
        print("Program stopped by user.")

    except Exception as error:
        print("Program failed because of an unexpected error.")
        print(f"Details: {error}")


if __name__ == "__main__":
    main()
