from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import os
import time

html = '''
<html>
<head>
    <style>
        body {
            width: 800px;
            height: 1200px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            display: flex;
            align-items: center;
            justify-content: center;
            font-family: Arial, sans-serif;
            margin: 0;
        }
        h1 {
            color: white;
            font-size: 80px;
            text-align: center;
            text-shadow: 3px 3px 6px rgba(0,0,0,0.3);
        }
    </style>
</head>
<body>
    <h1>DESARROLLADOR WEB</h1>
</body>
</html>
'''

# Guardar HTML temporalmente
with open('temp.html', 'w', encoding='utf-8') as f:
    f.write(html)

# Configurar Chrome en modo headless
chrome_options = Options()
chrome_options.add_argument('--headless')
chrome_options.add_argument('--window-size=800,1200')

# Crear driver
driver = webdriver.Chrome(options=chrome_options)
driver.get('file://' + os.path.abspath('temp.html'))
time.sleep(1)  # Esperar a que cargue

# Tomar screenshot
driver.save_screenshot('flyer.png')
driver.quit()

# Limpiar
os.remove('temp.html')

print("Flyer creado exitosamente!")