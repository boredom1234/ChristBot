from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from PIL import Image
import asyncio
import requests
import io
import cv2
import numpy as np
from mltu.inferenceModel import OnnxInferenceModel
from mltu.utils.text_utils import ctc_decoder
from mltu.configs import BaseModelConfigs
import time
import os
from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackContext

# Define your CAPTCHA-solving model class
class ImageToWordModel(OnnxInferenceModel):
    def __init__(self, model_path, char_list, *args, **kwargs):
        super().__init__(model_path=model_path, *args, **kwargs)
        self.char_list = char_list

    def predict(self, image):
        print(f"Input shapes: {self.input_shapes}")
        print(f"Image shape before resize: {image.shape}")

        if isinstance(self.input_shapes, list) and len(self.input_shapes) > 0:
            shape = self.input_shapes[0]
            if len(shape) == 4:
                height, width = shape[1], shape[2]
            elif len(shape) == 3:
                height, width = shape[0], shape[1]
            else:
                raise ValueError(f"Unexpected shape length: {len(shape)}")
        else:
            raise ValueError(f"Invalid input_shapes: {self.input_shapes}")

        image = cv2.resize(image, (width, height))
        print(f"Image shape after resize: {image.shape}")

        image_pred = np.expand_dims(image, axis=0).astype(np.float32)

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
        captcha_element = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, xpath))
        )
        time.sleep(5)
        
        captcha_image_url = captcha_element.get_attribute('src')
        
        if captcha_image_url:
            for attempt in range(3):
                response = requests.get(captcha_image_url)
                if response.status_code == 200:
                    image_path = 'captcha_image.png'
                    with open(image_path, 'wb') as file:
                        file.write(response.content)
                    return image_path
                else:
                    time.sleep(2)
        else:
            print("Captcha image URL is empty.")
    except Exception as e:
        print(f"Error in capturing CAPTCHA image: {e}")
    return None

def process_captcha_image(image_path):
    if image_path is None:
        return None
    
    configs = BaseModelConfigs.load("Models/02_captcha_to_text/202401211802/configs.yaml")
    model = ImageToWordModel(model_path=configs.model_path, char_list=configs.vocab)
    image = cv2.imread(image_path)
    if image is None:
        print("Failed to load image.")
        return None
    captcha_text = model.predict(image)
    return captcha_text

# Asynchronous command handlers
async def start(update: Update, context: CallbackContext):
    await update.message.reply_text('Welcome! Use /setcreds <username> <password> to set your credentials.')

async def setcreds(update: Update, context: CallbackContext):
    if len(context.args) != 2:
        await update.message.reply_text('Usage: /setcreds <username> <password>')
        return
    
    username, password = context.args
    user_id = str(update.message.from_user.id)
    
    # Save the username and password to a file
    with open(f'credentials_{user_id}.txt', 'w') as f:
        f.write(f'{username}\n{password}')
    
    await update.message.reply_text('Credentials saved. Use /run to execute the script.')

async def run(update: Update, context: CallbackContext):
    user_id = str(update.message.from_user.id)
    
    try:
        # Read credentials from file
        with open(f'credentials_{user_id}.txt', 'r') as f:
            username, password = f.read().strip().split('\n')

        # Initialize the Chrome driver
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))
        driver.set_window_size(1059, 772)
        driver.get("https://kp.christuniversity.in/KnowledgePro/StudentLogin.do")
        await asyncio.sleep(3)

        username_input = driver.find_element(By.ID, "username")
        username_input.click()
        username_input.send_keys(username)

        password_input = driver.find_element(By.ID, "password")
        password_input.send_keys(password)

        captcha_image_path = capture_captcha_image(driver, "/html/body/form/div[3]/div/div[1]/div/div/div[3]/div/div[3]/img[1]")
        captcha_text = process_captcha_image(captcha_image_path)

        if captcha_text:
            captcha_input = driver.find_element(By.ID, "captchaBox")
            captcha_input.click()
            captcha_input.send_keys(captcha_text)
            login_button = driver.find_element(By.XPATH, '//*[@id="Login"]/b')
            login_button.click()
            await asyncio.sleep(5)
            driver.get("https://kp.christuniversity.in/KnowledgePro/studentWiseAttendanceSummary.do?method=getIndividualStudentWiseSubjectAndActivityAttendanceSummary")
            await asyncio.sleep(5)
            content_element = driver.find_element(By.XPATH, "/html/body/div[2]/div")
            content_text = content_element.text
            await update.message.reply_text(f"Content:\n{content_text}")
        else:
            await update.message.reply_text("Failed to process CAPTCHA.")
        
        driver.quit()
    except Exception as e:
        await update.message.reply_text(f"An error occurred: {e}")

def main():
    TOKEN = '7302160357:AAFy35WO6Jc95tOhLqRua1d0icVMzatI5dk'  # Replace with your bot's token
    
    # Initialize the Application
    application = Application.builder().token(TOKEN).build()
    
    # Add command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("setcreds", setcreds))
    application.add_handler(CommandHandler("run", run))
    
    # Start polling
    application.run_polling()

if __name__ == '__main__':
    main()