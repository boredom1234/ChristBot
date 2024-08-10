from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from PIL import Image
import requests
import io
import cv2
import numpy as np
from mltu.inferenceModel import OnnxInferenceModel
from mltu.utils.text_utils import ctc_decoder
from mltu.configs import BaseModelConfigs
import time
import os

# Define your CAPTCHA-solving model class
class ImageToWordModel(OnnxInferenceModel):
    def __init__(self, model_path, char_list, *args, **kwargs):
        super().__init__(model_path=model_path, *args, **kwargs)
        self.char_list = char_list

    def predict(self, image):
        # Print input shapes and image shapes for debugging
        print(f"Input shapes: {self.input_shapes}")
        print(f"Image shape before resize: {image.shape}")

        # Extract dimensions from input_shapes
        if isinstance(self.input_shapes, list) and len(self.input_shapes) > 0:
            # Assume the first element is the relevant shape, adjust if needed
            shape = self.input_shapes[0]
            if len(shape) == 4:
                height, width = shape[1], shape[2]  # Extract height and width
            elif len(shape) == 3:
                height, width = shape[0], shape[1]  # For simpler shapes
            else:
                raise ValueError(f"Unexpected shape length: {len(shape)}")
        else:
            raise ValueError(f"Invalid input_shapes: {self.input_shapes}")

        # Resize image to match model input shape
        image = cv2.resize(image, (width, height))
        
        # Print image shape after resize for debugging
        print(f"Image shape after resize: {image.shape}")

        image_pred = np.expand_dims(image, axis=0).astype(np.float32)
        
        # Ensure input_names is a single string
        if isinstance(self.input_names, list):
            if len(self.input_names) == 1:
                input_name = self.input_names[0]
            else:
                raise ValueError("input_names list contains more than one item.")
        else:
            input_name = self.input_names

        preds = self.model.run(None, {input_name: image_pred})[0]
        text = ctc_decoder(preds, self.char_list)[0]
        return text

def capture_captcha_image(driver, xpath):
    try:
        # Find the captcha image element using XPath
        captcha_element = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, xpath))
        )
        # wait 5 seconds
        time.sleep(5)
        
        # Extract the captcha image URL from the src attribute
        captcha_image_url = captcha_element.get_attribute('src')
        
        print(f"Captcha image URL: {captcha_image_url}")  # Debugging line
        
        # Ensure the URL is valid and not empty
        if captcha_image_url:
            for attempt in range(3):  # Retry up to 3 times
                response = requests.get(captcha_image_url)
                print(f"Attempt {attempt + 1}: Fetching captcha image from: {captcha_image_url}")
                print(f"Response status code: {response.status_code}")
                print(f"Response content (first 100 chars): {response.content[:100]}")  # Log a snippet of the response content

                if response.status_code == 200:
                    # Save the image locally
                    image_path = 'captcha_image.png'
                    with open(image_path, 'wb') as file:
                        file.write(response.content)
                    return image_path  # Return the path to the saved image
                else:
                    print(f"Failed to retrieve captcha image. Status code: {response.status_code}")
                    time.sleep(2)  # Wait before retrying
        else:
            print("Captcha image URL is empty.")
    except Exception as e:
        print(f"Error in capturing CAPTCHA image: {e}")
    return None  # Return None if there's an issue

def process_captcha_image(image_path):
    if image_path is None:
        return None
    
    # Load model configurations
    configs = BaseModelConfigs.load("Models/02_captcha_to_text/202401211802/configs.yaml")

    # Initialize the model
    model = ImageToWordModel(model_path=configs.model_path, char_list=configs.vocab)

    # Read and process the CAPTCHA image
    image = cv2.imread(image_path)
    if image is None:
        print("Failed to load image.")
        return None
    
    captcha_text = model.predict(image)
    return captcha_text

# Initialize the Chrome driver
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))

try:
    # Set viewport size
    driver.set_window_size(1059, 772)

    # Navigate to the login page
    driver.get("https://kp.christuniversity.in/KnowledgePro/StudentLogin.do")
    time.sleep(3)  # Wait for the page to load

    # Enter username
    username_input = driver.find_element(By.ID, "username")
    username_input.click()
    username_input.send_keys("2347141")

    # Enter password
    password_input = driver.find_element(By.ID, "password")
    password_input.send_keys("86530920")

    # Capture CAPTCHA image
    captcha_image_path = capture_captcha_image(driver, "/html/body/form/div[3]/div/div[1]/div/div/div[3]/div/div[3]/img[1]")  # Adjust selector as needed
    captcha_text = process_captcha_image(captcha_image_path)

    if captcha_text:
        # Enter captcha
        captcha_input = driver.find_element(By.ID, "captchaBox")
        captcha_input.click()
        captcha_input.send_keys(captcha_text)

        # Click login button
        login_button = driver.find_element(By.XPATH, '//*[@id="Login"]/b')
        login_button.click()
        
        # Wait for login to complete
        time.sleep(5)
        
        # Navigate to the student attendance summary page
        driver.get("https://kp.christuniversity.in/KnowledgePro/studentWiseAttendanceSummary.do?method=getIndividualStudentWiseSubjectAndActivityAttendanceSummary")
        time.sleep(5)  # Wait for the page to load

        # Extract and print the contents
        content_element = driver.find_element(By.XPATH, "/html/body/div[2]/div")
        content_text = content_element.text
        print("Content of /html/body/div[2]/div:")
        # Replace 
        '''
        The medical leave will be considered only if aggregate % is above 75% at the end of semester. Medical leave will be applied between 75% and 85% of attendance with co-curricular
The attendance claimed for co-curricular, extra-curricular and departmental activities will be added to the total aggregate at the end of semester.

* Maximum percentage without leave
* Total Percentage=(Total Class Present/Total Class Conducted)*100
* Value added courses not included with ""
        '''
        content_text = content_text.replace("The medical leave will be considered only if aggregate % is above 75% at the end of semester. Medical leave will be applied between 75% and 85% of attendance with co-curricular", "The medical leave will be considered only if aggregate % is above 75% at the end of semester. Medical leave will be applied between 75% and 85% of attendance with co-curricular.")
        print(content_text)
        
    else:
        print("Failed to process CAPTCHA.")

finally:
    # Close the browser
    driver.quit()
