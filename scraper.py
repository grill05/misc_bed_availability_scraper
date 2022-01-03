from selenium import webdriver;
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver import ActionChains


import os,requests,time,bs4,datetime,csv;
from PIL import Image
import json

if __name__=='__main__':
  
  date=datetime.datetime.now();date_str=date.strftime('%Y-%m-%d')
  
  # ~ for city in ['delhi']:
  for city in ['hp','mp','chennai','pune','delhi']:
    if city=='bengaluru':
      #BENGALURU
      options=webdriver.ChromeOptions();
      options.add_argument('--ignore-certificate-errors');
      options.add_argument('--disable-gpu');
      options.add_argument("--headless")
      options.add_argument("--window-size=1366,768")
      driver=webdriver.Chrome(chrome_options=options)  
      driver.get('https://apps.bbmpgov.in/Covid19/en/bedstatus.php')
      driver.get('https://www.powerbi.com/view?r=eyJrIjoiOTcyM2JkNTQtYzA5ZS00MWI4LWIxN2UtZjY1NjFhYmFjZDBjIiwidCI6ImQ1ZmE3M2I0LTE1MzgtNGRjZi1hZGIwLTA3NGEzNzg4MmRkNiJ9')
      driver.get('20.186.65.100/view?r=eyJrIjoiOTcyM2JkNTQtYzA5ZS00MWI4LWIxN2UtZjY1NjFhYmFjZDBjIiwidCI6ImQ1ZmE3M2I0LTE1MzgtNGRjZi1hZGIwLTA3NGEzNzg4MmRkNiJ9')
      time.sleep(10)
      date=datetime.datetime.now();date_str=date.strftime('%d_%m_%Y')
      if not os.path.exists('images/'+date_str+'.png'):
        driver.save_screenshot('images/'+date_str+'.png')
        img=Image.open('images/'+date_str+'.png')
        img.save('images/'+date_str+'.webp')
        print('saved screenshot of bengaluru beds availability dashboard to %s' %('images/'+date_str+'.webp'))
      else:
        print('Image: %s already existed. Skipping!!' %('images/'+date_str+'.png'))
    elif city=='delhi':
      #check if data for given date already exists in csv. Update only if data doesn't exist
      a=open('data.delhi.csv');r=csv.reader(a);info=[i for i in r];a.close()
      dates=list(set([i[0] for i in info[1:]]));dates.sort()
      
      dont_update_data_csv=False
      if date_str in dates: 
            dont_update_data_csv=True
            print('----------\n\nData for %s already exists in csv!!\nOnly printing, not modifying csv!!\n\n----------\n\n' %(date_str))
      
      #get data
      y=str(requests.get('https://coronabeds.jantasamvad.org/covid-info.js').content);
      if y:
            y=json.loads(y[y.find('{'):y.rfind('}')+1].replace('\\n','').replace("\\'",''))
            info=''
            
            # ~ for bed_type in ['beds', 'oxygen_beds', 'covid_icu_beds', 'ventilators', 'icu_beds_without_ventilator', 'noncovid_icu_beds']:
            # ~ info+='%s,%s,%d,%d,%d\n' %(date_str,bed_type,y[bed_type]['All']['total'],y[bed_type]['All']['occupied'],y[bed_type]['All']['vacant'])
            info+='%s,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d' %(date_str,y['beds']['All']['total'],y['oxygen_beds']['All']['total'],y['covid_icu_beds']['All']['total'],y['ventilators']['All']['total'],y['icu_beds_without_ventilator']['All']['total'],y['noncovid_icu_beds']['All']['total'],y['beds']['All']['occupied'],y['oxygen_beds']['All']['occupied'],y['covid_icu_beds']['All']['occupied'],y['ventilators']['All']['occupied'],y['icu_beds_without_ventilator']['All']['occupied'],y['noncovid_icu_beds']['All']['occupied'])    
            #write to file
            a=open('data.delhi.csv','a')
            if not dont_update_data_csv:
                  a.write(info+'\n')
                  print('delhi: '+info)
                  a.close()
      else:
            print('could not get data from https://coronabeds.jantasamvad.org/covid-info.js')

    elif city=='pune':
      x=os.popen('curl -k https://divcommpunecovid.com/ccsbeddashboard/hsr').read()
      from bs4 import BeautifulSoup
      soup=BeautifulSoup(x,'html.parser');
      xx=soup('legend')[1].parent
      xx=xx('table')[0]
      tot_beds,vacant_beds,tot_normal,vacant_normal,tot_o2,vacant_o2,tot_icu,vacant_icu,tot_vent,vacant_vent=[i.text for i in xx('td') if i.text.isnumeric()]
      print(tot_beds,tot_normal,tot_o2,tot_icu,tot_vent,vacant_beds,vacant_normal,vacant_o2,vacant_icu,vacant_vent)
      occupied_normal=int(tot_normal)-int(vacant_normal)
      occupied_o2=int(tot_o2)-int(vacant_o2)
      occupied_icu=int(tot_icu)-int(vacant_icu)
      occupied_vent=int(tot_vent)-int(vacant_vent)
      row=(date_str,tot_normal,tot_o2,tot_icu,tot_vent,occupied_normal,occupied_o2,occupied_icu,occupied_vent)
      print(city+':')
      print(row)
    elif city=='hp':
      x=os.popen('curl -k https://covidcapacity.hp.gov.in/index.php').read()
      from bs4 import BeautifulSoup
      soup=BeautifulSoup(x,'html.parser');
      xx=soup('a',attrs={'id':'oxygenbedmodel'})[0]
      tot_o2=int(xx.parent.parent('td')[0].text)
      occupied_o2=int(xx.parent.parent('td')[1].text)
      xx=soup('a',attrs={'id':'icubedmodel'})[0]
      tot_icu=int(xx.parent.parent('td')[0].text)
      occupied_icu=int(xx.parent.parent('td')[1].text)
      xx=soup('a',attrs={'id':'Standardbedmodel'})[0]
      tot_normal=int(xx.parent.parent('td')[0].text)
      occupied_normal=int(xx.parent.parent('td')[1].text)
      row=(date_str,tot_normal,tot_o2,tot_icu,occupied_normal,occupied_o2,occupied_icu)
      print(city+':');print(row)
    elif city=='mp':
      x=os.popen('curl -k http://sarthak.nhmmp.gov.in/covid/facility-bed-occupancy-dashboard/').read()
      from bs4 import BeautifulSoup
      soup=BeautifulSoup(x,'html.parser');
      xx=soup('a',attrs={'href':'http://sarthak.nhmmp.gov.in/covid/facility-bed-occupancy-details'})
      tot_normal,occupied_normal,vacant_normal,tot_o2,occupied_o2,vacant_o2,tot_icu,occupied_icu,vacant_icu=[i.text for i in xx if i.text.isnumeric()]
      row=(date_str,tot_normal,tot_o2,tot_icu,occupied_normal,occupied_o2,occupied_icu)
      print(city+':');print(row)
    elif city=='chennai':
      #CHENNAI
      import requests
      from requests.structures import CaseInsensitiveDict
      
      url = "https://tncovidbeds.tnega.org/api/hospitals"
      
      headers = CaseInsensitiveDict()
      headers["authority"] = "tncovidbeds.tnega.org"
      #headers["sec-ch-ua"] = "" Not A;Brand";v="99", "Chromium";v="96", "Google Chrome";v="96""
      headers["dnt"] = "1"
      headers["sec-ch-ua-mobile"] = "?0"
      headers["user-agent"] = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.45 Safari/537.36"
      headers["content-type"] = "application/json;charset=UTF-8"
      headers["accept"] = "application/json, text/plain, */*"
      headers["token"] = "null"
      #headers["sec-ch-ua-platform"] = ""Linux""
      headers["sec-ch-ua-platform"] = "Linux"
      headers["origin"] = "https://tncovidbeds.tnega.org"
      headers["sec-fetch-site"] = "same-origin"
      headers["sec-fetch-mode"] = "cors"
      headers["sec-fetch-dest"] = "empty"
      headers["accept-language"] = "en-US,en;q=0.9"
      #headers["cookie"] = "_ga=GA1.2.1493856265.1640076462; _gid=GA1.2.514620938.1640076462; _gat=1"
      
      data = '{"searchString":"","sortCondition":{"Name":1},"pageNumber":1,"pageLimit":200,"SortValue":"Availability","ShowIfVacantOnly":"","Districts":["5ea0abd2d43ec2250a483a40"],"BrowserId":"6f4dfda2b7835796132d69d0e8525127","IsGovernmentHospital":true,"IsPrivateHospital":true,"FacilityTypes":["CHO"]}'
      
      
      resp = requests.post(url, headers=headers, data=data)
      
      print(resp.status_code)
      y=json.loads(resp.content.decode('unicode_escape').replace('\n',''))
      tot_o2_beds=0;tot_non_o2_beds=0;tot_icu_beds=0;
      occupied_o2_beds=0;occupied_non_o2_beds=0;occupied_icu_beds=0;
      vacant_o2_beds=0;vacant_non_o2_beds=0;vacant_icu_beds=0;
      
      for i in y['result']:
        tot_o2_beds+=i['CovidBedDetails']['AllotedO2Beds']
        tot_non_o2_beds+=i['CovidBedDetails']['AllotedNonO2Beds']
        tot_icu_beds+=i['CovidBedDetails']['AllotedICUBeds']
        occupied_o2_beds+=i['CovidBedDetails']['OccupancyO2Beds']
        occupied_non_o2_beds+=i['CovidBedDetails']['OccupancyNonO2Beds']
        occupied_icu_beds+=i['CovidBedDetails']['OccupancyICUBeds']
        vacant_o2_beds+=i['CovidBedDetails']['VaccantO2Beds']
        vacant_non_o2_beds+=i['CovidBedDetails']['VaccantNonO2Beds']
        vacant_icu_beds+=i['CovidBedDetails']['VaccantICUBeds']
      print('In Chennai, on %s\nO2: %d/%d occupied\nNon-O2 %d/%d occupied\nICU: %d/%d occupied' %(date_str,occupied_o2_beds,tot_o2_beds,occupied_non_o2_beds,tot_non_o2_beds,occupied_icu_beds,tot_icu_beds))
      
      
      a=open('data.chennai.csv');r=csv.reader(a);info=[i for i in r];a.close()
      dates=list(set([i[0] for i in info[1:]]));dates.sort()
      
      if date_str in dates: 
        # ~ dont_update_data_csv=True
        print('----------\n\nData for %s already exists in csv!!\nOnly printing, not modifying csv!!\n\n----------\n\n' %(date_str))
      else:
        #write to file
        info=', '.join((date_str,str(tot_o2_beds),str(tot_non_o2_beds),str(tot_icu_beds),str(occupied_o2_beds),str(occupied_non_o2_beds),str(occupied_icu_beds)))        
        a=open('data.chennai.csv','a');a.write(info+'\n');a.close()
        print('Appended to data.chennai.csv: '+info)        
    if city in ['mp','hp','pune']:
      csv_fname='data.'+city+'.csv'
      a=open(csv_fname);r=csv.reader(a);info=[i for i in r];a.close()
      dates=list(set([i[0] for i in info[1:]]));dates.sort()
      
      if date_str in dates: 
        # ~ dont_update_data_csv=True
        print('----------\n\nData for %s already exists in %s!!\nOnly printing, not modifying csv!!\n\n----------\n\n' %(date_str,csv_fname))
      else:
        #write to file
        a=open(csv_fname,'a');w=csv.writer(a);w.writerow(row);a.close()
        print('Appended to %s :%s' %(csv_fname,str(row)))        
  
