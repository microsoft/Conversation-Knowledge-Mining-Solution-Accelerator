from base.base import BasePage


class LoginPage(BasePage):

    EMAIL_TEXT_BOX = "//input[@type='email']"
    NEXT_BUTTON = "//input[@type='submit']"
    PASSWORD_TEXT_BOX = "//input[@type='password']"
    SIGNIN_BUTTON = "//input[@id='idSIButton9']"
    YES_BUTTON = "//input[@id='idSIButton9']"
    PERMISSION_ACCEPT_BUTTON = "//input[@type='submit']"

    def __init__(self, page):
        self.page = page

    def authenticate(self, username,password):
        # login with username and password in web url
        self.page.locator(self.EMAIL_TEXT_BOX).fill(username)
        self.page.locator(self.NEXT_BUTTON).click()
        # Wait for the password input field to be available and fill it
        self.page.wait_for_load_state('networkidle')
        # Enter password
        self.page.locator(self.PASSWORD_TEXT_BOX).fill(password)
        # Click on SignIn button
        self.page.locator(self.SIGNIN_BUTTON).click()
        # Wait for 5 seconds to ensure the login process completes
        self.page.wait_for_timeout(20000)  # Wait for 20 seconds
        if self.page.locator(self.PERMISSION_ACCEPT_BUTTON).is_visible():
            self.page.locator(self.PERMISSION_ACCEPT_BUTTON).click()
            self.page.wait_for_timeout(10000)
        else:
            # Click on YES button
            self.page.locator(self.YES_BUTTON).click()
            self.page.wait_for_timeout(10000)
        # Wait for the "Articles" button to be available and click it
        self.page.wait_for_load_state('networkidle')
