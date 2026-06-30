# Add PowerShell 7 to PATH in Windows

This guide will help you add **PowerShell 7** (PowerShell Core) to your system’s PATH variable on Windows, so you can easily run it from any Command Prompt or Run dialog.

## Prerequisites

- You should have **PowerShell 7** installed on your machine. If you haven’t installed it yet, you can download it following the guide here: [Installing PowerShell on Windows | Microsoft Learn](https://learn.microsoft.com/en-us/powershell/scripting/install/installing-powershell-on-windows?view=powershell-7.5).
- **Administrative privileges are not required** unless you're modifying system-wide environment variables. You can modify your **user-specific PATH** without admin rights.

## Steps to Add PowerShell 7 to PATH

### 1. Open **System Properties**
   - Press `Win + X` and choose **System**.
   - Click on **Advanced system settings** on the left sidebar. This will open the **System Properties** window.
   - In the **System Properties** window, click on the **Environment Variables** button at the bottom.

### 2. Edit User Environment Variables
   - In the **Environment Variables** window, under **User variables**, find the `Path` variable.
   - Select the `Path` variable and click **Edit**. (If the `Path` variable doesn’t exist, click **New** and name it `Path`.)

### 3. Check if PowerShell 7 Path is Already in PATH
   - Before adding the path, make sure the following path is not already present in the list:
     ```
     C:\Program Files\PowerShell\7\
     ```
   - If the path is already there, you don't need to add it again.

### 4. Add PowerShell 7 Path
   - If the path is not already in the list, click **New** in the **Edit Environment Variable** window.
   - Add the following path to the list:

     ```
     C:\Program Files\PowerShell\7\
     ```

   > **Note:** If you installed PowerShell 7 in a custom location, replace the above path with the correct one.

### 5. Save Changes
   - After adding the path, click **OK** to close the **Edit Environment Variable** window.
   - Click **OK** again to close the **Environment Variables** window.
   - Finally, click **OK** to exit the **System Properties** window.

### 6. Verify PowerShell 7 in PATH
   - Open **Command Prompt** or **Run** (press `Win + R`).
   - Type `pwsh` and press Enter.
   - If PowerShell 7 opens, you've successfully added it to your PATH!

---

## Troubleshooting

- **PowerShell 7 not opening:** Ensure the path to PowerShell 7 is entered correctly. If you're using a custom installation folder, check that the correct path is added to the `Path` variable.

- **Changes not taking effect:** Try restarting your computer or logging out and logging back in for the changes to apply.
