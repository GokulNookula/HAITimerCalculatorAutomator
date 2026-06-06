import csv
import os


def haiTaskListCSVCreator(taskDateDict: list, outputFolder: str = "Output", csvFileName: str = "hhTaskFileList.csv"):

    try:
        if taskDateDict is None:
            raise ValueError("taskDateDict is None. The scraper did not return task data.")

        # Create Output folder if it does not exist
        if not os.path.exists(outputFolder):
            os.makedirs(outputFolder)

        # CSV file path
        csvFilePath = os.path.join(outputFolder, csvFileName)

        # Check if CSV already exists
        fileExists = os.path.exists(csvFilePath)

        # Write CSV
        with open(csvFilePath, "w", newline="", encoding="utf-8") as file:

            writer = csv.DictWriter(file, fieldnames=["My Tasks", "Status", "Last worked on", "Total time", "Project Name", "Project Pay Per Hour", "HAI Email"])

            writer.writeheader()
            writer.writerows(taskDateDict)

        if fileExists:
            print(f"Updated existing CSV file: {csvFilePath}")
        else:
            print(f"Created new CSV file: {csvFilePath}")

        print(f"Saved {len(taskDateDict)} tasks.")

        return csvFilePath

    except PermissionError as error:
        print("CSV creation failed: Permission denied. Close the CSV file if it is currently open in Excel, then try again.")
        print(f"Python error: {error}")
        return None

    except OSError as error:
        print("CSV creation failed: Python could not create the output folder or write the CSV file.")
        print(f"Python error: {error}")
        return None

    except Exception as error:
        print("CSV creation failed because of an unexpected error.")
        print(f"Python error: {error}")
        return None
