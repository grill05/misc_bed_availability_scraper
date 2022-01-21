from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver import ActionChains
from tabula import read_pdf
import pandas as pd
from urllib.parse import unquote


import ast, os, requests, time, bs4, datetime, csv, colorama, sys
from PIL import Image
import json, time, re, pytz, tqdm
from bs4 import BeautifulSoup


# ~ global_proxy='socks4://157.119.201.231:1080'
# ~ global_proxy='socks4://103.88.221.194:46450'
# ~ global_proxy = "socks4://49.206.195.204:5678"
global_proxy = "socks4://111.90.175.13:5678"
# ~ if 'GLOBAL_PROXY' in os.environ: global_proxy=os.environ['GLOBAL_PROXY']

# Set timezone globally
os.environ["TZ"] = "Asia/Kolkata"
time.tzset()

def archive_raw_source(city,html_str):
    #test if archive already exists
    date = datetime.datetime.now();date_str = date.strftime("%Y-%m-%d")
    fname='raw_sources/'+city+'/'+date_str+'.zip'
    base_path=os.path.split(fname)[0]
    os.system('mkdir -pv '+base_path)
    if os.path.exists(fname):
        print('archive for city: %s already existed at %s. returning' %(city,fname));
        return
    else:
        import zipfile,zlib,bz2
        x=zipfile.ZipFile(fname,'w',compression=zipfile.ZIP_BZIP2)
        x.writestr('source.htm',html_str)
        x.close()
        print('created archive for city: %s in %s' %(city,fname));
        os.system('git config --global user.email "you@example.com" && git config --global user.name "Your Name" && git add --verbose '+base_path+' && git add --verbose '+fname )
        
def get_dataset_from_html_table(table):
    headings = [th.get_text() for th in table.find("tr").find_all("th")]
    datasets = []
    for row in table.find_all("tr")[1:]:
        dataset = list(zip(headings, (td.get_text() for td in row.find_all("td"))))
        datasets.append(dataset)
    return datasets


def highlight(text):
    highlight_begin = colorama.Back.BLACK + colorama.Fore.WHITE + colorama.Style.BRIGHT
    highlight_reset = (
        colorama.Back.RESET + colorama.Fore.RESET + colorama.Style.RESET_ALL
    )
    return highlight_begin + text + highlight_reset


def get_data_df(br):
    soup = BeautifulSoup(br.page_source, "html.parser")
    table = soup.find(
        "table",
        {
            "class": "style92",
            "style": "border-collapse: separate; border: solid black 1px; border-radius: 6px; -moz-border-radius: 6px;",
        },
    )

    rows = table.find_all("tr")
    ids = [x.get("id") for x in rows]
    ids_to_subset = [id for id in ids if id and id.endswith("_1")]
    data = []
    for row in rows:
        if row.get("id") in ids_to_subset:
            cols = row.find_all("td")
            cols = [ele.text.strip().replace("\n", " ") for ele in cols]
            data.append([ele.strip() for ele in cols if ele])  # Get rid of empty values
    data_df = pd.DataFrame(data)
    data_df.columns = ["hospital", "total_beds", "available_beds", "last_updated"]
    data_df.total_beds = data_df.total_beds.astype(int)
    data_df.available_beds = data_df.available_beds.astype(int)

    data_df["last_updated_date"] = pd.to_datetime(
        data_df["last_updated"].str.split(" ").str.get(0), format="%d/%m/%Y"
    )
    data_df = data_df.sort_values(by="last_updated_date")

    return data_df


def get_url_failsafe(u, timeout=25, out=""):
    if out:
        print(
            "downloading %s in get_url_failsafe to %s, timeout: %d sec"
            % (u, out, timeout)
        )
        x = os.popen(
            # ~ "curl --max-time " + str(timeout) + ' -# -k "' + u + '" -o "' + out + '"'
            "curl -s --max-time "
            + str(timeout)
            + '  -k "'
            + u
            + '" -o "'
            + out
            + '"'
        ).read()
    else:
        print(
            "downloading raw page %s in get_url_failsafe, timeout %d sec" % (u, timeout)
        )
        # ~ x = os.popen("curl --max-time " + str(timeout) + " -# -k " + u).read()
        x = os.popen("curl -s --max-time " + str(timeout) + "  -k " + u).read()
    if out and os.path.exists(out):
        x = True

    tries = 0
    while (not x) and tries < 10:
        print(
            "retrying download of %s in get_url_failsafe() for the %d -th time"
            % (u, tries + 1)
        )
        if out:
            x = os.popen(
                "curl --max-time "
                + str(2 * timeout)
                + " -x "
                + global_proxy
                # ~ + ' -# -k "'
                + ' -s -k "'
                + u
                + '" -o "'
                + out
                + '"'
            ).read()
        else:
            x = os.popen(
                "curl --max-time "
                + str(2 * timeout)
                + " -x "
                + global_proxy
                # ~ + ' -# -k "'
                + ' -s -k "'
                + u
                + '"'
            ).read()
        if out and os.path.exists(out):
            x = True
        tries += 1
    if not out:
        if x:
            soup = BeautifulSoup(x, "html.parser")
            return soup
        else:
            print(
                "Failed to download website: %s either directly(curl) or via proxy!!"
                % (u)
            )
    else:
        if not os.path.exists(out):
            print("Failed to save url:%s to file: %s" % (u, out))


def tamil_nadu_bulletin_parser(
    bulletin="",
    return_page_range=False,
    clip_bulletin=False,
    return_date=False,
    dump_clippings=False,
    return_beds_page=False,
    return_district_tpr_page=False,
):
    cmd = 'pdftotext  -layout "' + bulletin + '" tmp.txt'
    os.system(cmd)
    # ~ b=[i for i in open('tmp.txt').readlines() if i]
    b = [i for i in open("tmp.txt", encoding="utf-8", errors="ignore").readlines() if i]
    idx = 0
    page_count = 1
    page_range = []
    got_start = False
    bulletin_date = ""
    bd = [i for i in b if "edia bulletin" in i.lower()]
    bulletin_date_string = ""
    bulletin_date = ""
    if bd:
        bulletin_date = (
            bd[0].split("lletin")[1].strip().replace("-", ".").replace("/", ".")
        )
        bulletin_date_string = bulletin_date
        bulletin_date = datetime.datetime.strptime(bulletin_date, "%d.%m.%Y")
    if return_date:
        return bulletin_date

    for i in b:
        if "\x0c" in i:
            page_count += 1
        if return_beds_page and ("BED VACANCY DETAILS".lower() in i.lower()):
            return page_count


def tamil_nadu_parse_hospitalizations(
    bulletin="", use_converted_txt=False, verbose=False
):
    date_str = tamil_nadu_bulletin_parser(bulletin, return_date=True).strftime(
        "%Y-%m-%d"
    )
    beds_page = tamil_nadu_bulletin_parser(bulletin, return_beds_page=True)
    if not use_converted_txt:
        # hospitalization page
        os.system(
            "pdftotext -layout -f %d -l %d %s tmp.txt"
            % (beds_page, beds_page, bulletin)
        )
        b = [i.strip() for i in open("tmp.txt").readlines() if i.strip()]
    else:  # if forcing, use tmp2.txt
        b = [i.strip() for i in open("tmp2.txt").readlines() if i.strip()]
    start_idx = [i for i in range(len(b)) if "Ariyalur" in b[i]][0]
    end_idx = [i for i in range(len(b)) if "Virudhunagar" in b[i]][0]
    bb = b[start_idx : end_idx + 2][:-1]
    last_line = [
        i for i in range(len(b)) if "grand" in b[i].lower() and "total" in b[i].lower()
    ][0]
    if len(b[last_line].split()) > 3:
        last_line = b[last_line]
    else:
        last_line = "Grand Total " + b[last_line + 1]
    data = {}
    for i in bb:
        try:
            (
                district,
                tot_o2,
                tot_nono2,
                tot_icu,
                occ_o2,
                occ_nono2,
                occ_icu,
                vac_o2,
                vac_nono2,
                vac_icu,
                vac_net,
            ) = i.split()[1:]
        except:
            print(
                "unable to parse hosp page details for line: "
                + i
                + "in bulletin: "
                + bulletin
                + "\nRreutnring"
            )
            return (i, bb)
        data[district] = [tot_o2, tot_nono2, tot_icu, occ_o2, occ_nono2, occ_icu]
    (
        tot_o2,
        tot_nono2,
        tot_icu,
        occ_o2,
        occ_nono2,
        occ_icu,
        vac_o2,
        vac_nono2,
        vac_icu,
        vac_net,
    ) = last_line.split()[2:]
    data["All"] = [tot_o2, tot_nono2, tot_icu, occ_o2, occ_nono2, occ_icu]
    # ~ if verbose: pprint.pprint(data)
    # CCC page
    os.system(
        "pdftotext -layout -f %d -l %d %s tmp.txt"
        % (beds_page + 1, beds_page + 1, bulletin)
    )
    b = [i.strip() for i in open("tmp.txt").readlines() if i.strip()]
    start_idx = [i for i in range(len(b)) if "Ariyalur" in b[i]][0]
    end_idx = [i for i in range(len(b)) if "Virudhunagar" in b[i]][0]
    bb = b[start_idx : end_idx + 2][:-1]
    last_line = [
        i for i in range(len(b)) if "grand" in b[i].lower() and "total" in b[i].lower()
    ][0]
    if len(b[last_line].split()) > 4:
        last_line = b[last_line]
    else:
        last_line = "Grand Total " + b[last_line + 1]
    for i in bb:
        district, tot_ccc, occ_ccc, vac_ccc = i.split()[1:]
        data[district].extend([tot_ccc, occ_ccc])
    # ~ print(last_line)
    tot_ccc, occ_ccc, vac_ccc = last_line.split()[2:]
    data["All"].extend([tot_ccc, occ_ccc])
    if verbose:
        pprint.pprint(data)
    data2 = []
    for district in data:
        if not district == "All":
            x = data[district]
            data2.append(
                [date_str, district, x[0], x[1], x[2], x[6], x[3], x[4], x[5], x[7]]
            )
    x = data["All"]
    data2.append([date_str, "All", x[0], x[1], x[2], x[6], x[3], x[4], x[5], x[7]])
    a = open("hosp.csv", "a")
    w = csv.writer(a)
    for i in data2:
        w.writerow(i)
    a.close()
    return (data2, date_str)


def tamil_nadu_auto_parse_latest_bulletin():
    print("Downloading TN bulletin portal webpage")
    x = os.popen("curl -# -k https://stopcorona.tn.gov.in/daily-bulletin/").read()
    soup = BeautifulSoup(x, "html.parser")
    x = soup("div", attrs={"class": "information"})
    if not x:
        print("could not find information div in TN bulletin portal!!")
        return
    latest_bulletin_url = x[0]("li")[0]("a")[0]["href"].replace("http://", "https://")
    cmd = (
        'wget  --user-agent "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36" "'
        + latest_bulletin_url
        + '"'
    )
    print(cmd)
    os.system(cmd)
    pdf = [i for i in os.listdir(".") if i.endswith(".pdf")]
    if pdf:
        pdf = pdf[0]
    data, bulletin_date = tamil_nadu_parse_hospitalizations(pdf)
    # check if data for date already exists in csv. if not, then add
    a = open("tamil_nadu.csv")
    r = csv.reader(a)
    info = [i for i in r]
    a.close()
    dates = list(set([i[0] for i in info[1:] if len(i) > 0]))
    dates.sort()
    if bulletin_date not in dates:
        os.system("cat hosp.csv >> tamil_nadu.csv && rm -v hosp.csv " + pdf)
    else:
        print(
            "data for "
            + bulletin_date
            + " already existed in tamil_nadu.csv. Only printing, not writing"
        )
        [print(i) for i in data]
    os.system("rm -vf *.pdf")


def gurugram_bulletin_parser(bulletin=""):
    os.system('pdftotext -layout "' + bulletin + '" t.txt')
    b = [i.strip() for i in open("t.txt").readlines() if i.strip()]

    x = [i for i in b if "Dated" in i]
    if not x:
        print("could not get date in " + bulletin)
        return
    x = x[0].split("Dated")[-1].strip().split()[-1]
    x = x.replace("-", "/").replace("/04/10/2021", "04/10/2021")
    date = datetime.datetime.strptime(x, "%d/%m/%Y").strftime("%Y-%m-%d")

    x = [i for i in b if "found Negative" in i]
    x2 = [i for i in b if "found Positive" in i]
    if not x:
        print("could not get tests in " + bulletin)
        return
    tot_tests_to_date = int(x[0].split()[-1].strip()) + int(x2[0].split()[-1].strip())

    x = [i for i in b if "New Cases" in i]
    if not x:
        print("could not get new cases in " + bulletin)
        return
    cases = int(x[0].split()[-1].strip())

    # ~ tpr='%.2f' %(100*(float(cases)/tests));tpr=float(tpr)

    x = [i for i in b if "(DCH )" in i]
    if not x:  # some 2021 bulletins report combined value
        x = [i for i in b if "(DCH +DCHC)" in i]
        if not x:
            print("could not get DHC occupancy in " + bulletin)
            return
        dhc_dchc_occupied = int(x[0].split()[-1].strip())
    else:
        dhc_dchc_occupied = int(x[0].split()[-1].strip())
        x = [i for i in b if "(DCHC)" in i]
        if not x:
            print("could not get DCHC occupancy in " + bulletin)
            return
        # ~ dchc_occupied=int(x[0].split()[-1].strip())
        dhc_dchc_occupied += int(x[0].split()[-1].strip())

    x = [i for i in b if "(DCCC)" in i]
    if not x:
        print("could not get DCCC occupancy in " + bulletin)
        return
    dccc_occupied = int(x[0].split()[-1].strip())

    x = [i for i in b if "Home Isolation" in i]
    if not x:
        print("could not get Home isolation numbers in " + bulletin)
        return
    home_isolation = int(x[0].split()[-1].strip())

    # ~ return (date,cases,tot_tests_to_date,dhc_occupied,dchc_occupied,dccc_occupied,home_isolation)
    return (
        date,
        cases,
        tot_tests_to_date,
        dhc_dchc_occupied,
        dccc_occupied,
        home_isolation,
    )


def gurugram_auto_parse_latest_bulletin():
    print("Downloading gurugram bulletin portal webpage")
    x = os.popen("curl -# -k https://gurugram.gov.in/health-bulletin/").read()
    soup = BeautifulSoup(x, "html.parser")
    x = soup("div", attrs={"class": "status-publish"})
    if not len(x) > 0:
        print("cold not find div from gurugram bulletin portal!!")
        return
    latest_bulletin_url = x[0]("li")[0]("a")[0]["href"]
    cmd = (
        'wget -q --user-agent "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36" "'
        + latest_bulletin_url
        + '"'
    )
    print(cmd)
    os.system(cmd)
    pdf = [i for i in os.listdir(".") if i.endswith(".pdf")]
    if pdf:
        pdf = pdf[0]
    row = gurugram_bulletin_parser(pdf)
    bulletin_date = row[0]

    # check if data for date already exists in csv. if not, then add
    a = open("gurugram.csv")
    r = csv.reader(a)
    info = [i for i in r]
    a.close()
    dates = list(set([i[0] for i in info[1:] if len(i) > 0]))
    dates.sort()
    if bulletin_date not in dates:
        a = open("gurugram.csv", "a")
        w = csv.writer(a)
        w.writerow(row)
        a.close()
    else:
        print(
            "data for "
            + bulletin_date
            + " already existed in gurugram.csv. Only printing, not writing"
        )
        print(row)
    os.system('rm -v "' + pdf + '" *.pdf')


def mumbai_bulletin_auto_parser(bulletin="", proxy=global_proxy):
    if not bulletin:  # download latest bulletin
        # ~ cmd='wget --no-check-certificate --user-agent "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36" "https://stopcoronavirus.mcgm.gov.in/assets/docs/Dashboard.pdf"'
        cmd = 'curl -# --max-time 15  -O -# -k -A "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36" "https://stopcoronavirus.mcgm.gov.in/assets/docs/Dashboard.pdf"'
        print(cmd)
        os.system(cmd)
        if os.path.exists("Dashboard.pdf"):
            bulletin = "Dashboard.pdf"

    max_tries = 10
    tries = 0
    if os.path.exists(bulletin):
        print("todays bulletin already exists.nothing to download")
    else:
        while (not os.path.exists(bulletin)) and (tries < max_tries):
            cmd = (
                'curl -# --max-time 60 -O  -k -x "'
                + proxy
                + '" "https://stopcoronavirus.mcgm.gov.in/assets/docs/Dashboard.pdf"'
            )
            print(cmd)
            os.system(cmd)
            if os.path.exists("Dashboard.pdf"):
                bulletin = "Dashboard.pdf"  # download through proxy worked

            os.system("ls -a *.pdf")
            tries += 1
        if os.path.exists("Dashboard.pdf"):
            bulletin = "Dashboard.pdf"  # download through proxy worked

    # get date
    cmd = (
        'pdftotext -x 10 -y 150 -W 200 -H 200 -layout -f 1 -l 1  "'
        + bulletin
        + '" t.txt'
    )
    os.system(cmd)
    b = [i.strip().replace(",", "") for i in open("t.txt").readlines() if i.strip()]

    date = [i.replace(",", "") for i in b if "2021" in i or "2022" in i]
    if not date:
        print("could not get date from " + bulletin)
    else:
        date = datetime.datetime.strptime(date[0], "%b %d %Y")
        date_str = date.strftime("%Y-%m-%d")

    # get cases,tests,symp etc
    cmd = (
        'pdftotext -x 0 -y 100 -W 220 -H 320 -layout -f 2 -l 2 "' + bulletin + '" t.txt'
    )
    os.system(cmd)
    b = [i.strip().replace(",", "") for i in open("t.txt").readlines() if i.strip()]

    cases = [i for i in b if "positive" in i.lower()]
    if not cases:
        print("could not get cases from " + bulletin)
    else:
        cases = int(cases[0].split()[-1].strip())

    active = [i for i in b if "active" in i.lower()]
    if not active:
        print("could not get actives from " + bulletin)
    else:
        active = int(active[0].split()[-1].strip())

    asymp = [i for i in b if "Asymptomatic" in i]
    if not asymp:
        print("could not get asymp from " + bulletin)
    else:
        asymp = int(asymp[0].split()[-1].strip())

    symp = [i for i in b if "Symptomatic" in i]
    if not symp:
        print("could not get symp from " + bulletin)
    else:
        symp = int(symp[0].split()[-1].strip())

    critical = [i for i in b if "critical" in i.lower()]
    if not critical:
        print("could not get criticals from " + bulletin)
    else:
        critical = int(critical[0].split()[-1].strip())

    tests = [i for i in b if "tests" in i.lower()]
    if not tests:
        print("could not get tests from " + bulletin)
    else:
        tests = int(tests[0].split()[-1].strip())

    # get hospital occupancy
    cmd = (
        'pdftotext -x 340 -y 100 -W 95 -H 340 -layout -f 2 -l 2 "'
        + bulletin
        + '" t.txt'
    )
    os.system(cmd)
    b = [i.strip().replace(",", "") for i in open("t.txt").readlines() if i.strip()]

    if not (
        "2021" in b[0] or "2022" in b[0] or "2021" in b[1] or "2022" in b[1]
    ):  # means date wasn't at top, parsed wrong
        print("could not parse occupancy numbers")
    else:
        for j in range(len(b)):
            if b[j] and b[j][0].isnumeric():
                b = b[j:]
                break
        try:
            bc, bo, ba, dc, do, da, oc, oo, oa, ic, io, ia, vc, vo, va = [
                i for i in b if i
            ]
        except:
            print("failed to get occupancy split")
            return b
        gen_beds_cap = int(bc)
        gen_beds_occupancy = int(bo)
        o2_cap = int(oc)
        o2_occupancy = int(oo)
        icu_cap = int(ic)
        icu_occupancy = int(io)
        vent_cap = int(vc)
        vent_occupancy = int(vo)

    row = (
        date_str,
        cases,
        tests,
        o2_cap,
        icu_cap,
        vent_cap,
        o2_occupancy,
        icu_occupancy,
        vent_occupancy,
        gen_beds_cap,
        gen_beds_occupancy,
        active,
        symp,
        asymp,
        critical,
    )
    # ~ a=open('tmp.csv','a');w=csv.writer(a);w.writerow(row);a.close()

    # check if data for date already exists in csv. if not, then add
    a = open("mumbai.csv")
    r = csv.reader(a)
    info = [i for i in r]
    a.close()
    dates = list(set([i[0] for i in info[1:] if len(i) > 0]))
    dates.sort()
    print("Mumbai data:")
    if date_str not in dates:
        a = open("mumbai.csv", "a")
        w = csv.writer(a)
        w.writerow(row)
        a.close()
    else:
        print(
            "data for "
            + date_str
            + " already existed in mumbai.csv. Only printing, not writing"
        )
    print(row)

    os.system('rm -v "' + bulletin + '"')
    # ~ return b
    return row


if __name__ == "__main__":

    failed_cities = []
    all_cities = [
        "bengaluru",
        "hp",
        "mp",
        "chennai",
        "pune",
        "delhi",
        "gbn",
        "gurugram",
        "tn",
        "mumbai",
        "chandigarh",
        "uttarakhand",
        "kerala",
        "ap",
        "telangana",
        "nagpur",
        "nashik",
        "gandhinagar",
        "vadodara",
        "wb",
        "pb",
        "jammu",
        "goa",
        "bihar",
        "rajasthan",
        "ludhiana",
        "jamshedpur",
        "jharkhand",
        "meghalaya",
        "up",
        "manipur",
        "pgimer",
        "ahmedabad",
        "puducherry",
        "ladakh",
        "chhattisgarh",
        "nagaland",
        "an",
    ]

    # override all_cities if one particular city in sys.argv[-1]
    if sys.argv[-1] in all_cities:
        all_cities = [sys.argv[-1].strip()]
    # List of cities for which the generic writing logic should be executed
    generic_writer_cities = [
        "mp",
        "hp",
        "pune",
        "chandigarh",
        "uttarakhand",
        "kerala",
        "ap",
        "telangana",
        "nagpur",
        "nashik",
        "gandhinagar",
        "vadodara",
        "wb",
        "pb",
        "jammu",
        "goa",
        "bihar",
        "rajasthan",
        "ludhiana",
        "jamshedpur",
        "jharkhand",
        "meghalaya",
        "manipur",
        "up",
        "pgimer",
        "ahmedabad",
        "puducherry",
        "ladakh",
        "chhattisgarh",
        "an",
    ]
    # all_cities = [all_cities[-1]]  # Uncomment this to run on the last city/state added
    # generic_writer_cities = [
    #    generic_writer_cities[-1]
    # ]  # uncomment this to run the generic writing logic on last city added
    print("all cities: {}".format(all_cities))
    if len(all_cities) > 2:
        print("generic writer cities: {}".format(generic_writer_cities))

    # MAIN LOOP
    for city in all_cities:
        # ~ for city in ['up']:
        print("running scraper for: " + city)
        date = datetime.datetime.now()
        date_str = date.strftime("%Y-%m-%d")
        try:
            if city == "bengaluru":
                # BENGALURU

                url = "https://apps.bbmpgov.in/Covid19/en/mediabulletin.php"

                response = requests.get(url)
                soup = BeautifulSoup(response.text, "html.parser")
                links = soup.find_all("a")

                for link in links:
                    if ".pdf" in link.get("href", []):
                        print("Downloading pdf...")

                        l = "https://apps.bbmpgov.in/Covid19/en/" + link.get(
                            "href"
                        ).replace(" ", "%20")
                        print(l)
                        response = requests.get(l)
                        pdf = open("BLR_" + str(date_str) + ".pdf", "wb")
                        pdf.write(response.content)
                        pdf.close()
                        break
                # get date from bulletin
                os.system("pdftotext -layout  BLR_" + str(date_str) + ".pdf t.txt")
                b = [i.strip() for i in open("t.txt").readlines() if i.strip()]
                date_line = [i for i in b if "WAR ROOM".lower() in i.lower()]
                if not date_line:
                    print(
                        "could not get date from bengaluru buletin BLR_"
                        + str(date_str)
                        + ".pdf !!"
                    )
                    sys.exit(1)
                bulletin_date = datetime.datetime.strptime(
                    date_line[0].split("/")[-2].strip(), "%d.%m.%Y"
                ).strftime("%Y-%m-%d")

                # get page for bed status
                page_count = 0
                beds_page = 0
                b = [i for i in open("t.txt").readlines() if i.strip()]
                for i in b:
                    if "\x0c" in i:
                        page_count += 1
                    if "COVID BED STATUS".lower() in i.lower():
                        beds_page = page_count + 1
                        break
                # ~ print(beds_page)

                # print(text)
                tables = read_pdf(
                    "BLR_" + str(date_str) + ".pdf", pages=beds_page, silent=True
                )
                dff = tables[0]

                results = []
                raw_line = " ".join(
                    [str(i).replace(",", "") for i in list(dff.iloc[len(dff) - 1])]
                )
                x = [i for i in raw_line.split() if i.isnumeric()]
                (
                    general_available,
                    hdu_available,
                    icu_available,
                    ventilator_available,
                ) = x[1:5]
                general_admitted, hdu_admitted, icu_admitted, ventilator_admitted = x[
                    6:10
                ]

                a = open("data.bengaluru.csv")
                r = csv.reader(a)
                info = [i for i in r]
                a.close()
                dates = list(set([i[0] for i in info[1:]]))
                dates.sort()

                info = ", ".join(
                    (
                        bulletin_date,
                        str(general_available),
                        str(general_admitted),
                        str(hdu_available),
                        str(hdu_admitted),
                        str(icu_available),
                        str(icu_admitted),
                        str(ventilator_available),
                        str(ventilator_admitted),
                    )
                )

                os.system("rm -vf BLR_" + str(date_str) + ".pdf *.pdf")
                if bulletin_date in dates:
                    # ~ dont_update_data_csv=True
                    print(
                        "----------\n\nData for %s already exists in data.bengaluru.csv!!\nOnly printing, not modifying csv!!\n\n----------\n\n"
                        % (date_str)
                    )
                    print("bengaluru: " + str(info))
                else:
                    # write to file

                    a = open("data.bengaluru.csv", "a")
                    a.write(info + "\n")
                    a.close()
                    print("Appended to data.bengaluru.csv: " + info)

            elif city == "pgimer":
                soup = get_url_failsafe(
                    "https://pgimer.edu.in/PGIMER_PORTAL/PGIMERPORTAL/GlobalPages/JSP/covidDashboardyy.jsp"
                )

                report_date = ",".join(
                    (
                        ":".join(
                            soup.select("#lblLast_Update")[0].text.split(":")[1:]
                        ).split()
                    )[:3]
                ).replace(",,", ",")
                report_date_str = datetime.datetime.strptime(
                    report_date, "%b,%d,%Y"
                ).strftime("%Y-%m-%d")
                for body in soup("tbody"):
                    body.unwrap()
                x = pd.read_html(str(soup), flavor="bs4")

                icu, hdu, step_down, pediatric, others = list(
                    x[0].loc[len(x[0]) - 1].astype(int)
                )

                male, female = x[1].loc[len(x[1]) - 1].astype(int)

                if x[2].loc[1][0].startswith("0"):  # 0-12 type
                    u12, u40, u60, u80, plus80 = list(x[2].loc[2].astype(int))
                else:  # 0,1-.. type
                    u1, u12, u40, u60, u80, plus80 = list(x[2].loc[2].astype(int))
                    u12 += u1

                chandigarh = punjab = haryana = himachal = other_states = 0

                y = [
                    i[1] for i in x[3].to_dict("split")["data"] if i[0] == "Chandigarh"
                ]
                if y:
                    chandigarh = y[0]
                y = [i[1] for i in x[3].to_dict("split")["data"] if i[0] == "Punjab"]
                if y:
                    punjab = y[0]
                y = [i[1] for i in x[3].to_dict("split")["data"] if i[0] == "Haryana"]
                if y:
                    haryana = y[0]
                y = [
                    i[1]
                    for i in x[3].to_dict("split")["data"]
                    if i[0] == "Himachal Pradesh"
                ]
                if y:
                    himachal = y[0]
                y = [
                    i[1]
                    for i in x[3].to_dict("split")["data"]
                    if i[0]
                    not in ["Himachal Pradesh", "Haryana", "Punjab", "Chandigarh"]
                ]
                if y:
                    other_states = sum([int(i) for i in y if i.isnumeric()])

                (
                    cumulative_icu,
                    cumulative_hdu,
                    cumulative_step_down,
                    cumulative_pediatric,
                    cumulative_others,
                ) = list(x[4].loc[len(x[4]) - 1].astype(int))

                cumulative_male, cumulative_female = x[5].loc[len(x[5]) - 1].astype(int)

                if x[6].loc[1][0].startswith("0"):  # 0-12 type
                    (
                        cumulative_u12,
                        cumulative_u40,
                        cumulative_u60,
                        cumulative_u80,
                        cumulative_plus80,
                    ) = list(x[6].loc[2].astype(int))
                else:  # 0,1-.. type
                    (
                        cumulative_u1,
                        cumulative_u12,
                        cumulative_u40,
                        cumulative_u60,
                        cumulative_u80,
                        cumulative_plus80,
                    ) = list(x[6].loc[2].astype(int))
                    cumulative_u12 += cumulative_u1

                cumulative_chandigarh = (
                    cumulative_punjab
                ) = (
                    cumulative_haryana
                ) = cumulative_himachal = cumulative_other_states = 0

                y = [
                    i[1] for i in x[7].to_dict("split")["data"] if i[0] == "Chandigarh"
                ]
                if y:
                    cumulative_chandigarh = y[0]
                y = [i[1] for i in x[7].to_dict("split")["data"] if i[0] == "Punjab"]
                if y:
                    cumulative_punjab = y[0]
                y = [i[1] for i in x[7].to_dict("split")["data"] if i[0] == "Haryana"]
                if y:
                    cumulative_haryana = y[0]
                y = [
                    i[1]
                    for i in x[7].to_dict("split")["data"]
                    if i[0] == "Himachal Pradesh"
                ]
                if y:
                    cumulative_himachal = y[0]
                y = [
                    i[1]
                    for i in x[7].to_dict("split")["data"]
                    if i[0]
                    not in ["Himachal Pradesh", "Haryana", "Punjab", "Chandigarh"]
                ]
                if y:
                    cumulative_other_states = sum([int(i) for i in y if i.isnumeric()])

                discharged, deaths, d2, d3 = x[8].loc[2].astype(int).unique()
                deaths += d2 + d3

                row = (
                    report_date_str,
                    icu,
                    hdu,
                    step_down,
                    pediatric,
                    others,
                    male,
                    female,
                    u12,
                    u40,
                    u60,
                    u80,
                    plus80,
                    chandigarh,
                    punjab,
                    haryana,
                    himachal,
                    other_states,
                    cumulative_icu,
                    cumulative_hdu,
                    cumulative_step_down,
                    cumulative_pediatric,
                    cumulative_others,
                    cumulative_male,
                    cumulative_female,
                    cumulative_u12,
                    cumulative_u40,
                    cumulative_u60,
                    cumulative_u80,
                    cumulative_plus80,
                    cumulative_chandigarh,
                    cumulative_punjab,
                    cumulative_haryana,
                    cumulative_himachal,
                    cumulative_other_states,
                    discharged,
                    deaths,
                )
                print(city + ":")
                print(row)
                archive_raw_source(city,str(soup))
            elif city == "ahmedabad":
                url = "https://ahmedabadcity.gov.in/portal/COVID19.jsp"
                options = webdriver.ChromeOptions()
                options.add_argument("--ignore-certificate-errors")
                options.add_argument("--headless")
                br = webdriver.Chrome(chrome_options=options)
                br.get(url)
                soup = BeautifulSoup(br.page_source, "html.parser")
                for body in soup("tbody"):
                    body.unwrap()

                dfs = pd.read_html(str(soup), flavor="bs4")
                dff = dfs[0]
                (
                    isolation_beds,
                    o2_beds,
                    icu_ventilator_beds,
                    icu_nonventilator_beds,
                ) = dff.iloc[0].tolist()
                row = (
                    date_str,
                    isolation_beds,
                    o2_beds,
                    icu_ventilator_beds,
                    icu_nonventilator_beds,
                )
                print(city + ":")
                print(row)
                os.system("rm -rf *.pdf")
                archive_raw_source(city,str(soup))
            elif city == "puducherry":
                date = datetime.datetime.now()
                date_str = date.strftime("%Y-%m-%d")
                options = webdriver.ChromeOptions()
                options.add_argument("--ignore-certificate-errors")
                options.add_argument("--headless")
                br = webdriver.Chrome(chrome_options=options)
                br.get("https://covid19dashboard.py.gov.in/BedAvailabilityDetails")

                soup = BeautifulSoup(br.page_source, "html.parser")
                for body in soup("tbody"):
                    body.unwrap()

                dfs = pd.read_html(str(soup), flavor="bs4")
                dff = dfs[0]
                (
                    isolation_beds_total,
                    isolation_beds_vacant,
                    o2_beds_total,
                    o2_beds_vacant,
                    ventilator_beds_total,
                    ventilator_beds_vacant,
                ) = dff.iloc[-1].tolist()[2:]

                occupied_isolation_beds = int(isolation_beds_total) - int(
                    isolation_beds_vacant
                )
                occupied_o2_beds = int(o2_beds_total) - int(o2_beds_vacant)
                occupied_ventilator_beds = int(ventilator_beds_total) - int(
                    ventilator_beds_vacant
                )

                row = (
                    date_str,
                    isolation_beds_total,
                    occupied_isolation_beds,
                    o2_beds_total,
                    occupied_o2_beds,
                    ventilator_beds_total,
                    occupied_ventilator_beds,
                )
                print(city + ":")
                print(row)
                archive_raw_source(city,str(soup))
            elif city == "ladakh":
                date = datetime.datetime.now()
                date_str = date.strftime("%Y-%m-%d")
                options = webdriver.ChromeOptions()
                options.add_argument("--ignore-certificate-errors")
                options.add_argument("--headless")
                br = webdriver.Chrome(chrome_options=options)
                br.get("http://covid.ladakh.gov.in")

                soup = BeautifulSoup(br.page_source, "html.parser")

                for body in soup("tbody"):
                    body.unwrap()
                dfs = pd.read_html(str(soup), flavor="bs4")
                dff = dfs[0]

                ventilators_and_icu_occupied = int(
                    dff["Ventilator/ICU"].sum(skipna=True)
                )
                o2_beds_occupied = int(dff["Oxygen Supported"].sum(skipna=True))
                normal_beds_occupied = int(dff["Normal"].sum(skipna=True))
                total_beds_vacant = int(dff["Total Vaccant Beds"].sum(skipna=True))

                row = (
                    date_str,
                    o2_beds_occupied,
                    ventilators_and_icu_occupied,
                    normal_beds_occupied,
                    total_beds_vacant,
                )
                print(city + ":")
                print(row)
                archive_raw_source(city,str(soup))
            elif city == "chhattisgarh":
                date = datetime.datetime.now()
                date_str = date.strftime("%Y-%m-%d")

                options = webdriver.ChromeOptions()
                options.add_argument("--ignore-certificate-errors")
                options.add_argument("--headless")
                #page requires proxy
                # ~ options.add_argument('--proxy-server='+global_proxy)

                br = webdriver.Chrome(chrome_options=options)
                br.get("https://govthealth.cg.gov.in/")
                soup = BeautifulSoup(br.page_source, "html.parser")

                district_element = br.find_element_by_name(
                    "ctl00$MainContent$ddDistrict"
                )
                district_element.send_keys("0")  # for all districts
                submit = br.find_element_by_name("ctl00$MainContent$btnSearch")
                submit.click()

                soup = BeautifulSoup(br.page_source, "html.parser")
                # tables = soup.find_all("table")

                for body in soup("tbody"):
                    body.unwrap()

                dfs = pd.read_html(str(soup), flavor="bs4")
                dff = dfs[1]
                new_header = dff.iloc[0]  # grab the first row for the header
                dff = dff[1:]  # take the data less the header row
                dff.columns = new_header  # set the header row as the df header
                dff.loc[:, "Bed Type"] = (
                    dff["Bed Type"].str.lower().str.replace(" ", "_")
                )
                dff = dff.set_index("Bed Type")
                dff.columns = dff.columns.str.lower()
                dff = dff.applymap(int)
                keys = ["vacant", "full", "total"]
                data = [date_str]
                labels = ["date_str"]
                for index, row in dff.iterrows():
                    for key in keys:
                        data.append(row[key])
                        labels.append("{}_{}".format(index, key))
                row = tuple(data)

                print(city + ":")
                print(row)
                archive_raw_source(city,str(soup))

            elif city == "an":
                districts_of_interest = [
                    "North & Middle Andaman",
                    "South Andaman",
                    "Nicobar",
                ]
                soup = get_url_failsafe("https://dhs.andaman.gov.in/")

                links = soup.find_all("a", {"target": "_blank"})
                date = datetime.datetime.now()
                date_str_target = date.strftime("%d/%m/%Y")

                link_target_text = "A&N ISLANDS HEALTH BULLETIN FOR CONTAINMENT OF COVID-19 ({})".format(
                    date_str_target
                )
                shortlist_link = [
                    a["href"] for a in links if a.text.startswith(link_target_text)
                ]

                if len(shortlist_link):
                    an_pdf = "https://dhs.andaman.gov.in/" + "/" + shortlist_link[0]
                    date = datetime.datetime.now()
                    date_str = date.strftime("%Y-%m-%d")

                    print("Downloading pdf..." + an_pdf)

                    response = requests.get(an_pdf)
                    bulletin = "Andaman_" + str(date_str) + ".pdf"
                    pdf = open(bulletin, "wb")
                    pdf.write(response.content)
                    pdf.close()

                    try:
                        tables = read_pdf(bulletin, pages=1, silent=True)
                    except CalledProcessError:
                        pass

                    cmd = 'pdftotext  -layout "' + bulletin + '" tmp.txt'
                    os.system(cmd)
                    b = [
                        i
                        for i in open(
                            "tmp.txt", encoding="utf-8", errors="ignore"
                        ).readlines()
                        if i
                    ]
                    os.system("rm -vf tmp.txt {}".format(bulletin))
                    date_line = "COVID-19 STATUS OF ANDAMAN & NICOBAR ISLANDS AS ON"
                    bulletin_date = None
                    for line in b:
                        if line.startswith(date_line):
                            bulletin_date = line.split(date_line)[1].strip()
                            bulletin_date = datetime.datetime.strptime(
                                bulletin_date, "%d.%m.%Y"
                            ).strftime("%Y-%m-%d")
                            break
                    if bulletin_date is not None:
                        for table in tables:
                            if table.columns[1] == "Isolation Beds":
                                table.columns = [
                                    "district",
                                    "isolation_beds",
                                    "occupied_beds",
                                    "vacant_beds",
                                ]
                                df = table.loc[
                                    table.district.isin(districts_of_interest)
                                ]
                                df["isolation_beds"] = pd.to_numeric(
                                    df["isolation_beds"], errors="coerce"
                                )
                                df["occupied_beds"] = pd.to_numeric(
                                    df["occupied_beds"], errors="coerce"
                                )
                                df["vacant_beds"] = pd.to_numeric(
                                    df["vacant_beds"], errors="coerce"
                                )

                                totals = (
                                    df.loc[
                                        :,
                                        [
                                            "isolation_beds",
                                            "occupied_beds",
                                            "vacant_beds",
                                        ],
                                    ]
                                    .sum(skipna=True)
                                    .astype(int)
                                    .tolist()
                                )
                                row = (bulletin_date, totals[0], totals[1], totals[2])
                                break
                    print(city + ":")
                    print(row)
            elif city == "nagaland":
                date = datetime.datetime.now()
                date_str = date.strftime("%Y-%m-%d")
                options = webdriver.ChromeOptions()
                options.add_argument("--ignore-certificate-errors")
                options.add_argument("--headless")
                br = webdriver.Chrome(chrome_options=options)
                br.get("https://covid19.nagaland.gov.in/charts")

                soup = BeautifulSoup(br.page_source, "lxml")
                archive_raw_source(city,str(soup))
                scpt = soup.select("script")

                for itern, s in enumerate(scpt):
                    if len(s.contents) > 0 and "var h_data = " in s.contents[0]:
                        hospitalization_data_tmp = (
                            s.contents[0]
                            .split("var h_data = ")[1]
                            .split(";")[0]
                            .replace(", ]", "]")
                            .replace("[ ", "[")
                            .replace(",  ,", ",  'NA',")
                        )
                        hospitalization_data_parsed = ast.literal_eval(
                            hospitalization_data_tmp
                        )
                        hospitalization_data = pd.to_numeric(
                            hospitalization_data_parsed, errors="coerce"
                        ).astype(float)
                        hospitalization_data[hospitalization_data < 0] = float("nan")
                        hospitalization_data = hospitalization_data.tolist()
                        labels_tmp = (
                            s.contents[0]
                            .split("var label = ")[1]
                            .split(";")[0]
                            .replace(", ]", "]")
                            .replace("[ ", "[")
                        )
                        labels_tmp = (
                            s.contents[0]
                            .split("var label = ")[1]
                            .split(";")[0]
                            .replace(", ]", "]")
                            .replace("[ ", "[")
                        )
                        labels_parsed = ast.literal_eval(labels_tmp)
                        # if it is not in [Jan, Feb, March, April] it must be from 2021
                        months_2021 = [
                            "May",
                            "Jun",
                            "Jul",
                            "Aug",
                            "Sep",
                            "Oct",
                            "Nov",
                            "Dec",
                        ]
                        dates = []
                        for date in labels_parsed:
                            if date[-3:] in months_2021:
                                date_unformatted = date + " 2021"

                            else:
                                date_unformatted = date + " 2022"

                            date_formatted = datetime.datetime.strptime(
                                date_unformatted, "%d %b %Y"
                            )
                            date_str = date_formatted.strftime("%Y-%m-%d")

                            dates.append(date_str)
                        data = pd.DataFrame.from_dict(
                            dict(zip(dates, hospitalization_data)),
                            orient="index",
                            columns=["total_hospitalization"],
                        )
                        data.total_hospitalization = data.total_hospitalization.astype(
                            "Int64"
                        )
                        data.index.name = "date"
                        if not os.path.exists("data.nagaland.csv"):
                            data = data.reset_index()
                            data.to_csv("data.nagaland.csv", index=False, header=True)
                        existing_data = pd.read_csv("data.nagaland.csv", index_col=0)
                        existing_data.index.name = "date"
                        existing_data.total_hospitalization = (
                            existing_data.total_hospitalization.astype("Int64")
                        )
                        # do not change old entries
                        already_present_index = data.index.intersection(
                            existing_data.index
                        )
                        # are there new dates?
                        missing_index = data.index.difference(existing_data.index)
                        if len(missing_index):
                            existing_data = existing_data.append(
                                data.loc[missing_index, :]
                            )

                            existing_data = existing_data.reset_index()

                            existing_data.to_csv(
                                "data.nagaland.csv",
                                index=False,
                                header=True,
                            )
                        break
            elif city == "pb":
                soup = get_url_failsafe(
                    "https://phsc.punjab.gov.in/en/covid-19-notifications"
                )
                links = [
                    i["href"]
                    for i in soup("a")
                    if i.has_attr("href") and ".xlsx" in i["href"]
                ]
                link_date = [
                    i.text
                    for i in soup("a")
                    if i.has_attr("href") and ".xlsx" in i["href"]
                ][0]
                date_str = datetime.datetime.strptime(
                    link_date.split()[link_date.split().index("on") + 1], "%d-%m-%Y"
                ).strftime("%Y-%m-%d")

                os.system('curl -# -k "' + links[0] + '" -o tmp.xlsx')
                os.system("ssconvert tmp.xlsx tmp.csv")
                x = pd.read_csv("tmp.csv")
                archive_str=open('tmp.csv').read()
                summary = list(x.iloc[len(x) - 1][3:-4])
                tot_o2 = int(summary[0])
                tot_icu = int(summary[8])
                tot_vent = int(summary[13])
                occupied_normal = int(summary[3]) + int(summary[5])
                occupied_o2 = int(summary[0]) - int(summary[1])
                occupied_icu = int(summary[8]) - int(summary[9])
                occupied_vent = int(summary[13]) - int(summary[14])

                os.system('curl -# -k "' + links[1] + '" -o tmp.xlsx')
                os.system("ssconvert tmp.xlsx tmp.csv")
                archive_str+='\n\n\n'+open('tmp.csv').read()
                x = pd.read_csv("tmp.csv")
                summary = list(x.iloc[len(x) - 1][3:-4])
                tot_o2 += int(summary[0])
                tot_icu += int(summary[8])
                tot_vent += int(summary[13])
                occupied_normal += int(summary[3]) + int(summary[5])
                occupied_o2 += int(summary[0]) - int(summary[1])
                occupied_icu += int(summary[8]) - int(summary[9])
                occupied_vent += int(summary[13]) - int(summary[14])
                os.system("rm -vf tmp.csv tmp.xlsx")

                row = (
                    date_str,
                    tot_o2,
                    tot_icu,
                    tot_vent,
                    occupied_normal,
                    occupied_o2,
                    occupied_icu,
                    occupied_vent,
                )
                print(city + ":")
                print(row)
                archive_raw_source(city,archive_str)

            elif city == "tn":
                tamil_nadu_auto_parse_latest_bulletin()
            elif city == "gurugram":
                gurugram_auto_parse_latest_bulletin()
            elif city == "rajasthan":
                soup = get_url_failsafe(
                    "https://covidinfo.rajasthan.gov.in/Covid-19hospital-wisebedposition-wholeRajasthan.aspx",
                    105,
                )
                y = pd.read_html(str(soup("table")[0]), flavor="bs4")[0]
                recent_update = [
                    list(y.iloc[i])
                    for i in range(1, len(y))
                    if str(list(y.iloc[i])[-1]).split()[0] != "nan"
                    and datetime.datetime.strptime(
                        str(list(y.iloc[i])[-1]).split()[0], "%d-%m-%Y"
                    )
                    >= datetime.datetime.now() - datetime.timedelta(days=2)
                ]
                # ~ hosp = [
                # ~ " ".join([j.text for j in row("td")])
                # ~ for row in soup("table")[0]("tr")
                # ~ ][3:]
                # ~ recent_update = [
                # ~ i
                # ~ for i in hosp
                # ~ if i.split()[-1] != "N/A"
                # ~ and datetime.datetime.strptime(i.split()[-2], "%d-%m-%Y")
                # ~ >= datetime.datetime.now() - datetime.timedelta(days=2)
                # ~ ]
                tot_normal = 0
                tot_o2 = 0
                tot_icu = 0
                tot_vent = 0
                occupied_normal = 0
                occupied_o2 = 0
                occupied_icu = 0
                occupied_vent = 0
                for i in recent_update:
                    try:
                        (
                            tot_normal0,
                            occupied_normal0,
                            x1,
                            tot_o20,
                            occupied_o20,
                            x2,
                            tot_icu0,
                            occupied_icu0,
                            x3,
                            tot_vent0,
                            occupied_vent0,
                            x4,
                        ) = i[3:15]
                        tot_normal += int(tot_normal0)
                        tot_o2 += int(tot_o20)
                        tot_icu += int(tot_icu0)
                        tot_vent += int(tot_vent0)
                        occupied_normal += int(occupied_normal0)
                        occupied_o2 += int(occupied_o20)
                        occupied_icu += int(occupied_icu0)
                        occupied_vent += int(occupied_vent0)
                    except:
                        print("in parsing rajasthan failed for hospital " + str(i))
                row = (
                    date_str,
                    tot_normal,
                    tot_o2,
                    tot_icu,
                    tot_vent,
                    occupied_normal,
                    occupied_o2,
                    occupied_icu,
                    occupied_vent,
                )
                print(city + ":")
                print(row)
                archive_raw_source(city,str(soup))
            elif city == "up":
                options = webdriver.ChromeOptions()
                options.add_argument("--ignore-certificate-errors")
                options.add_argument("--headless")
                br = webdriver.Chrome(chrome_options=options)
                # ~ print('downloading main UP page..')
                br.get("https://beds.dgmhup-covid19.in/EN/covid19bedtrack")
                # ~ print('downloaded main UP page..')
                soup = BeautifulSoup(br.page_source, "html.parser")
                select_districts = soup.find(
                    "select", {"id": "MainContent_EN_ddDistrict"}
                )
                districts = [opt.text for opt in select_districts.find_all("option")][
                    1:
                ]
                # br.close()
                dfs = []

                pbar = tqdm.tqdm(districts)
                for district in pbar:
                    pbar.set_description("parsing for UP district: " + district)
                    try:
                        district_element = br.find_element_by_name(
                            "ctl00$MainContent_EN$ddDistrict"
                        )
                        district_element.send_keys(district)

                        facility_element = br.find_element_by_name(
                            "ctl00$MainContent_EN$ddFacility"
                        )
                        facility_element.send_keys("All")

                        facilitytype_element = br.find_element_by_name(
                            "ctl00$MainContent_EN$ddFacilityType"
                        )
                        facilitytype_element.send_keys("All Type")

                        bedavail = br.find_element_by_name(
                            "ctl00$MainContent_EN$ddBedAva"
                        )
                        bedavail.send_keys("All")

                        submit = br.find_element_by_name("ctl00$MainContent_EN$Button2")
                        submit.click()
                        hospital_df = get_data_df(br)
                        hospital_df["district"] = district
                        dfs.append(hospital_df)
                    except:
                        print("Failed for district: " + district)
                br.close()
                all_dfs = pd.concat(dfs)
                all_dfs["diff"] = all_dfs["total_beds"] - all_dfs["available_beds"]

                all_dfs = all_dfs.sort_values(by="diff", ascending=[False])

                all_dfs2 = (
                    all_dfs.loc[
                        :, ["last_updated_date", "total_beds", "available_beds"]
                    ]
                    .groupby("last_updated_date")
                    .agg(sum)
                )
                tot_normal, occupied_normal = all_dfs2[-3:].sum()
                row = (date_str, tot_normal, occupied_normal)
                print(city + ":")
                print(row)

                # ~ all_dfs.to_pickle('tmp.pickle')
                # ~ print(all_dfs2)
            elif city == "manipur":
                x = get_url_failsafe("https://nrhmmanipur.org/?page_id=5788")
                links = [
                    i["href"]
                    for i in x.select("#content")[0]("a")
                    if i.has_attr("href")
                    and "status report of patients" in i.text.lower()
                ]
                if links:
                    x = get_url_failsafe(links[0])
                    x = get_url_failsafe(links[0])
                else:
                    print("no links found for manipur")
                    continue
                links = [
                    i["href"]
                    for i in x.select("#content")[0]("a")
                    if i.has_attr("href") and "click here" in i.text.lower()
                ]
                if links:
                    # ~ get_url_failsafe(links[0],out='manipur_'+str(date_str)+'.pdf')
                    # pdf redirects, does not download directly
                    os.system(
                        'wget "' + links[0] + '" -O "manipur_' + str(date_str) + '.pdf"'
                    )
                    x = read_pdf(
                        "manipur_" + str(date_str) + ".pdf", silent=True, pages=1
                    )
                    x = x[0]
                    raw_line = " ".join(
                        [
                            str(x).split(".")[0].strip()
                            for x in list(x.iloc[len(x) - 2])
                            if str(x) != "nan"
                        ]
                    )
                    raw_line = [i for i in raw_line.split() if i.isnumeric()]
                    tot_normal, tot_icu = raw_line[:2]
                    vacant_normal, vacant_icu, vacant_all = raw_line[-3:]
                    occupied_normal = int(tot_normal) - int(vacant_normal)
                    occupied_icu = int(tot_icu) - int(vacant_icu)
                    report_date = os.path.split(links[0])[1]
                    report_date = report_date.split("Report_")[1].split("_")[0]
                    report_date_str = datetime.datetime.strptime(
                        report_date, "%d-%m-%Y"
                    ).strftime("%Y-%m-%d")
                    row = (
                        report_date_str,
                        tot_normal,
                        tot_icu,
                        occupied_normal,
                        occupied_icu,
                    )
                    print(city + ":")
                    print(row)
                else:
                    print("no links (in download area) found for manipur")
                    continue
                os.system("rm -v *pdf")
            elif city == "meghalaya":
                megh_pdf = "http://www.nhmmeghalaya.nic.in/img/icons/Daily%20Covid%2019%20Status%20in%20Hospitals.pdf"
                print("Downloading pdf..." + megh_pdf)
                x = get_url_failsafe(
                    megh_pdf, out="Meghalaya_" + str(date_str) + ".pdf", timeout=20
                )
                try:
                    tables = read_pdf(
                        "Meghalaya_" + str(date_str) + ".pdf", pages=1, silent=True
                    )
                except CalledProcessError:
                    pass
                dff = tables[0]
                if "COVID STATUS IN HOSPITALS IN THE STATE AS ON" in dff.columns[1]:
                    report_date_str = dff.columns[1].split(" ")[-1].replace(".", "-")
                    report_date_str = (
                        datetime.datetime.strptime(report_date_str, "%d-%m-%Y")
                        .date()
                        .strftime("%Y-%m-%d")
                    )
                raw_line = " ".join(
                    [x.strip() for x in list(dff.iloc[len(dff) - 1]) if str(x) != "nan"]
                )
                (
                    beds_without_o2,
                    tot_o2,
                    tot_icu,
                    tot_all,
                    tot_occupied,
                    tot_vacant,
                ) = raw_line.split(" ")[1:]
                os.system("rm -v *pdf")
                row = (report_date_str, tot_all, tot_occupied)
                print(city + ":")
                print(row)

            elif city == "jharkhand":
                soup = get_url_failsafe(
                    "http://jrhms.jharkhand.gov.in/news-press-releases"
                )
                links = soup.find_all("a", {"target": "_blank"})
                date = datetime.datetime.now()
                date_str = date.strftime("%Y-%m-%d")
                downloaded_first_pdf = False

                for link in links:
                    if downloaded_first_pdf:
                        break
                    if ".pdf" in link.get("href", []):
                        print("Downloading pdf...")
                        l = "http://jrhms.jharkhand.gov.in/" + link.get("href")
                        print(l)
                        get_url_failsafe(l, out="Jharkhand_" + str(date_str) + ".pdf")
                        # ~ response = requests.get(l)
                        # ~ pdf = open("Jharkhand_" + str(date_str) + ".pdf", "wb")
                        # ~ pdf.write(response.content)
                        # ~ pdf.close()
                        downloaded_first_pdf = True

                        try:
                            tables = read_pdf(
                                "Jharkhand_" + str(date_str) + ".pdf",
                                pages=2,
                                silent=True,
                            )
                        except CalledProcessError:
                            print("CalledProcessError when parsing Jharkhand pdf!")
                            continue
                        dff = tables[0]
                        if "Bed Status" in " ".join(dff.columns):
                            raw_line = " ".join(list(dff.iloc[len(dff) - 1])).strip()
                            (
                                tot_o2,
                                occupied_o2,
                                tot_icu,
                                occupied_icu,
                                tot_vent,
                                occupied_vent,
                            ) = raw_line.split(" ")[-6:]

                            report_date_str = (
                                unquote(l).split("/")[-1].split(".pdf")[0].split(" ")[0]
                            )
                            report_date_str = (
                                datetime.datetime.strptime(report_date_str, "%d-%m-%Y")
                                .date()
                                .strftime("%Y-%m-%d")
                            )
                            row = (
                                report_date_str,
                                tot_o2,
                                tot_icu,
                                tot_vent,
                                occupied_o2,
                                occupied_icu,
                                occupied_vent,
                            )
                            print(city + ":")
                            print(row)

                os.system("rm -v *pdf")
            elif city == "jamshedpur":
                options = webdriver.ChromeOptions()
                options.add_argument("--ignore-certificate-errors")
                options.add_argument("--headless")
                br = webdriver.Chrome(chrome_options=options)
                br.get("https://xlri.edu/covid19/bed-status/")
                soup = BeautifulSoup(br.page_source, "html.parser")
                cards = soup.select(".card")
                vacant_normal, tot_normal = cards[0]("p")[1].text.split("/")
                occupied_normal = int(tot_normal) - int(vacant_normal)
                vacant_o2, tot_o2 = cards[1]("p")[1].text.split("/")
                occupied_o2 = int(tot_o2) - int(vacant_o2)
                vacant_icu, tot_icu = cards[2]("p")[1].text.split("/")
                occupied_icu = int(tot_icu) - int(vacant_icu)
                vacant_vent, tot_vent = cards[3]("p")[1].text.split("/")
                occupied_vent = int(tot_vent) - int(vacant_vent)
                row = (
                    date_str,
                    tot_normal,
                    tot_o2,
                    tot_icu,
                    tot_vent,
                    occupied_normal,
                    occupied_o2,
                    occupied_icu,
                    occupied_vent,
                )
                print(city + ":")
                print(row)
                archive_raw_source(city,str(soup))
            elif city == "bihar":
                soup = get_url_failsafe(
                    "https://covid19health.bihar.gov.in/DailyDashboard/BedsOccupied", 60
                )
                datasets = get_dataset_from_html_table(soup("table")[0])

                regularly_updated = [
                    "MADHEPURA",
                    "PATNA",
                    "BHAGALPUR",
                    "DARBHANGA",
                    "MUZAFFARPUR",
                ]
                hosp = [
                    i
                    for i in datasets
                    if i[0][1] in regularly_updated and i[3][1] == "DCH"
                ]

                tot_beds = 0
                vacant_beds = 0
                tot_icu = 0
                vacant_icu = 0
                for i in hosp:
                    tot_beds += int(i[5][1])
                    vacant_beds += int(i[6][1])
                    tot_icu += int(i[7][1])
                    vacant_icu += int(i[8][1])
                occupied_beds = tot_beds - vacant_beds
                occupied_icu = tot_icu - vacant_icu

                row = (date_str, tot_beds, tot_icu, occupied_beds, occupied_icu)
                print(city + ":")
                print(row)
                archive_raw_source(city,str(soup))

            elif city == "gandhinagar":
                soup = get_url_failsafe(
                    "https://vmc.gov.in/HospitalModuleGMC/Default.aspx"
                )
                x1, x2, x3, vt, vo, vv, it, io, iv, ot, oo, ov, nt, no, nv = [
                    i.text
                    for i in soup("table")[0]("span")
                    if i.has_attr("id") and i["id"].startswith("lb")
                ]
                row = (date_str, nt, ot, it, vt, no, oo, io, vo)
                print(city + ":")
                print(row)

            elif city == "vadodara":
                soup = get_url_failsafe(
                    "https://vmc.gov.in/covid19vadodaraapp/Default.aspx"
                )
                x1, x2, x3, vt, vo, vv, it, io, iv, ot, oo, ov, nt, no, nv, x5 = [
                    i.text
                    for i in soup("table")[0]("span")
                    if i.has_attr("id") and i["id"].startswith("lb")
                ]
                row = (date_str, nt, ot, it, vt, no, oo, io, vo)
                print(city + ":")
                print(row)
                archive_raw_source(city,str(soup))
           
            elif city == "wb":
                soup = get_url_failsafe(
                    "https://excise.wb.gov.in/chms/Portal_Default.aspx"
                )
                x1, nc, nv, x2 = [
                    i.text.strip() for i in soup("span", attrs={"class": "counter"})
                ]
                no = int(nc) - int(nv)
                row = (date_str, nc, no)
                print(city + ":")
                print(row)
            elif city == "nashik":
                soup = get_url_failsafe(
                    "https://covidcbrs.nmc.gov.in/home/hospitalSummary"
                )
                x1, x2, x3, x4, nt, nv, ot, ov, it, iv, vt, vv = [
                    i.text.strip() for i in soup("tfoot")[0]("th")
                ]
                no = int(nt) - int(nv)
                oo = int(ot) - int(ov)
                io = int(it) - int(iv)
                vo = int(vt) - int(vv)
                row = (date_str, nt, ot, it, vt, no, oo, io, vo)
                print(city + ":")
                print(row)
                archive_raw_source(city,str(soup))
            elif city == "goa":
                soup = get_url_failsafe("https://goaonline.gov.in/beds")
                table = soup("table")[1]
                headings = [th.get_text() for th in table.find("tr").find_all("th")]
                datasets = []
                for row in table.find_all("tr")[1:]:
                    dataset = list(
                        zip(headings, (td.get_text() for td in row.find_all("td")))
                    )
                    datasets.append(dataset)
                # rest of hosp. not updated
                x = [
                    i
                    for i in datasets
                    if i[1][1]
                    in [
                        "Goa Medical College & Hospital, Bambolim",
                        "Victor Hospital, Margao",
                    ]
                ]
                tot_normal = sum([int(i[2][1]) for i in x])
                vacant_normal = sum([int(i[3][1]) for i in x])
                occupied_normal = tot_normal - vacant_normal
                tot_icu = sum([int(i[4][1]) for i in x])
                vacant_icu = sum([int(i[5][1]) for i in x])
                occupied_icu = tot_icu - vacant_icu
                row = (date_str, tot_normal, tot_icu, occupied_normal, occupied_icu)
                print(city + ":")
                print(row)
                archive_raw_source(city,str(soup))
            elif city == "jammu":
                soup = get_url_failsafe(
                    "https://covidrelief.jk.gov.in/Beds/Hospitals/JAMMU"
                )
                jammu_hospitals = [
                    "https://covidrelief.jk.gov.in/Beds/Hospitals/Hospital/609382b4f64c7a2d446721ec",
                    "https://covidrelief.jk.gov.in/Beds/Hospitals/Hospital/609381cbb1c6502bfe8c3c5f",
                    "https://covidrelief.jk.gov.in/Beds/Hospitals/Hospital/60938338f64c7a2d446721ee",
                    "https://covidrelief.jk.gov.in/Beds/Hospitals/Hospital/6093826ef64c7a2d446721eb",
                    "https://covidrelief.jk.gov.in/Beds/Hospitals/Hospital/609a4aa4dc9ca218af2fa243",
                    "https://covidrelief.jk.gov.in/Beds/Hospitals/Hospital/60bb02f17b6808683a6284e0",
                ]
                tnc = tic = tno = too = tio = 0
                for hospital in jammu_hospitals:
                    soup = get_url_failsafe(hospital)
                    try:
                        x1, x2, x3, nc, nv, ic, iv, oo = [
                            i("td")[1].text
                            for i in soup("table")[0]("tr")
                            if len(i("td")) > 1
                        ]
                        no = int(nc) - int(nv)
                        tno += no
                        tnc += int(nc)
                        io = int(ic) - int(iv)
                        tio += io
                        tic += int(ic)
                    except:
                        print("failed for " + hospital)
                        # ~ print(soup)

                row = (date_str, tnc, tic, tno, too, tio)
                print(city + ":")
                print(row)
            elif city == "nagpur":

                soup = get_url_failsafe("https://nsscdcl.org/covidbeds/", 20)
                oa = (
                    soup("div", attrs={"class": "small-box"})[0]("button")[0]
                    .text.split(":")[1]
                    .strip()
                )
                oo = (
                    soup("div", attrs={"class": "small-box"})[0]("label")[0]
                    .text.split(":")[1]
                    .strip()
                )
                oc = int(oa) + int(oo)

                na = (
                    soup("div", attrs={"class": "small-box"})[1]("button")[0]
                    .text.split(":")[1]
                    .strip()
                )
                no = (
                    soup("div", attrs={"class": "small-box"})[1]("label")[0]
                    .text.split(":")[1]
                    .strip()
                )
                nc = int(na) + int(no)

                ia = (
                    soup("div", attrs={"class": "small-box"})[2]("button")[0]
                    .text.split(":")[1]
                    .strip()
                )
                io = (
                    soup("div", attrs={"class": "small-box"})[2]("label")[0]
                    .text.split(":")[1]
                    .strip()
                )
                ic = int(ia) + int(io)

                va = (
                    soup("div", attrs={"class": "small-box"})[3]("button")[0]
                    .text.split(":")[1]
                    .strip()
                )
                vo = (
                    soup("div", attrs={"class": "small-box"})[3]("label")[0]
                    .text.split(":")[1]
                    .strip()
                )
                vc = int(va) + int(vo)

                row = (date_str, nc, oc, ic, vc, no, oo, io, vo)
                print(city + ":")
                print(row)
                archive_raw_source(city,str(soup))
            elif city == "mumbai":
                mumbai_bulletin_auto_parser()
            elif city == "gbn":
                # check if data for given date already exists in csv. Update only if data doesn't exist
                a = open("data.gbn.csv")
                r = csv.reader(a)
                info = [i for i in r]
                a.close()
                dates = list(set([i[0] for i in info[1:] if len(i) > 0]))
                dates.sort()

                dont_update_data_csv = False
                if date_str in dates:
                    dont_update_data_csv = True
                    print(
                        "----------\n\nData for %s already exists in csv!!\nOnly printing, not modifying csv!!\n\n----------\n\n"
                        % (date_str)
                    )

                # get data
                import requests
                from requests.structures import CaseInsensitiveDict

                url = "https://api.gbncovidtracker.in/hospitals"

                headers = CaseInsensitiveDict()
                headers["Connection"] = "keep-alive"
                headers["Accept"] = "application/json, text/plain, */*"
                headers["DNT"] = "1"
                headers["sec-ch-ua-mobile"] = "?0"
                headers[
                    "User-Agent"
                ] = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.45 Safari/537.36"
                headers["sec-ch-ua-platform"] = "Linux"
                headers["Origin"] = "https://gbncovidtracker.in"
                headers["Sec-Fetch-Site"] = "same-site"
                headers["Sec-Fetch-Mode"] = "cors"
                headers["Sec-Fetch-Dest"] = "empty"
                headers["Referer"] = "https://gbncovidtracker.in/"
                headers["Accept-Language"] = "en-US,en;q=0.9"

                resp = requests.get(url, headers=headers)
                # ~ print('api call status code: ', resp.status_code)

                y = resp.json()

                if y:
                    tot_beds = 0
                    tot_o2_beds = 0
                    tot_ventilator_beds = 0
                    occupied_beds = 0
                    occupied_o2_beds = 0
                    occupied_ventilator_beds = 0

                    for i in y:
                        tot_beds += int(i["normal"])
                        tot_o2_beds += int(i["oxygen"])
                        tot_ventilator_beds += int(i["ventilator"])
                        occupied_beds += int(i["normal"]) - int(i["Vacant_normal"])
                        occupied_o2_beds += int(i["oxygen"]) - int(i["Vacant_oxygen"])
                        occupied_ventilator_beds += int(i["ventilator"]) - int(
                            i["Vacant_ventilator"]
                        )

                    # ~ for bed_type in ['beds', 'oxygen_beds', 'covid_icu_beds', 'ventilators', 'icu_beds_without_ventilator', 'noncovid_icu_beds']:
                    info = "%s,%d,%d,%d,%d,%d,%d\n" % (
                        date_str,
                        tot_beds,
                        tot_o2_beds,
                        tot_ventilator_beds,
                        occupied_beds,
                        occupied_o2_beds,
                        occupied_ventilator_beds,
                    )

                    # write to file
                    a = open("data.gbn.csv", "a")
                    if not dont_update_data_csv:
                        a.write(info + "\n")
                    print("gbn: " + info)
                    a.close()
                else:
                    print(
                        "could not get data from https://api.gbncovidtracker.in/hospitals"
                    )

            elif city == "delhi":
                # check if data for given date already exists in csv. Update only if data doesn't exist
                a = open("data.delhi.csv")
                r = csv.reader(a)
                info = [i for i in r]
                a.close()
                dates = list(set([i[0] for i in info[1:]]))
                dates.sort()

                dont_update_data_csv = False
                if date_str in dates:
                    dont_update_data_csv = True
                    print(
                        "----------\n\nData for %s already exists in data.delhi.csv!!\nOnly printing, not modifying csv!!\n\n----------\n\n"
                        % (date_str)
                    )

                # get data
                y = str(
                    requests.get(
                        "https://coronabeds.jantasamvad.org/covid-info.js"
                    ).content
                )
                if y:
                    y = json.loads(
                        y[y.find("{") : y.rfind("}") + 1]
                        .replace("\\n", "")
                        .replace("\\'", "")
                    )
                    info = ""

                    # ~ for bed_type in ['beds', 'oxygen_beds', 'covid_icu_beds', 'ventilators', 'icu_beds_without_ventilator', 'noncovid_icu_beds']:
                    # ~ info+='%s,%s,%d,%d,%d\n' %(date_str,bed_type,y[bed_type]['All']['total'],y[bed_type]['All']['occupied'],y[bed_type]['All']['vacant'])
                    info += "%s,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d" % (
                        date_str,
                        y["beds"]["All"]["total"],
                        y["oxygen_beds"]["All"]["total"],
                        y["covid_icu_beds"]["All"]["total"],
                        y["ventilators"]["All"]["total"],
                        y["icu_beds_without_ventilator"]["All"]["total"],
                        y["noncovid_icu_beds"]["All"]["total"],
                        y["beds"]["All"]["occupied"],
                        y["oxygen_beds"]["All"]["occupied"],
                        y["covid_icu_beds"]["All"]["occupied"],
                        y["ventilators"]["All"]["occupied"],
                        y["icu_beds_without_ventilator"]["All"]["occupied"],
                        y["noncovid_icu_beds"]["All"]["occupied"],
                    )
                    print("delhi: " + info)

                    # write to file
                    if not dont_update_data_csv:
                        a = open("data.delhi.csv", "a")
                        a.write(info + "\n")
                        a.close()
                    archive_raw_source(city,json.dumps(y))
                else:
                    print(
                        "could not get data from https://coronabeds.jantasamvad.org/covid-info.js"
                    )

            elif city == "pune":
                soup = get_url_failsafe(
                    "https://divcommpunecovid.com/ccsbeddashboard/hsr"
                )
                xx = soup("legend")[1].parent
                xx = xx("table")[0]
                (
                    tot_beds,
                    vacant_beds,
                    tot_normal,
                    vacant_normal,
                    tot_o2,
                    vacant_o2,
                    tot_icu,
                    vacant_icu,
                    tot_vent,
                    vacant_vent,
                ) = [i.text for i in xx("td") if i.text.isnumeric()]
                print(
                    tot_beds,
                    tot_normal,
                    tot_o2,
                    tot_icu,
                    tot_vent,
                    vacant_beds,
                    vacant_normal,
                    vacant_o2,
                    vacant_icu,
                    vacant_vent,
                )
                occupied_normal = int(tot_normal) - int(vacant_normal)
                occupied_o2 = int(tot_o2) - int(vacant_o2)
                occupied_icu = int(tot_icu) - int(vacant_icu)
                occupied_vent = int(tot_vent) - int(vacant_vent)
                row = (
                    date_str,
                    tot_normal,
                    tot_o2,
                    tot_icu,
                    tot_vent,
                    occupied_normal,
                    occupied_o2,
                    occupied_icu,
                    occupied_vent,
                )
                print(city + ":")
                print(row)
                archive_raw_source(city,str(soup))
            elif city == "ap":
                try:
                    options = webdriver.ChromeOptions()
                    options.add_argument("--ignore-certificate-errors")
                    options.add_argument("--headless")
                    br = webdriver.Chrome(chrome_options=options)
                    br.get("http://dashboard.covid19.ap.gov.in/ims/hospbed_reports//")
                    time.sleep(9); #allow page to load fully
                    soup = BeautifulSoup(br.page_source, "html.parser")
                    for body in soup("tbody"): body.unwrap()
                    x=pd.read_html(str(soup),flavor='bs4')
                    if not x:
                        print('Could not find "Table" element in Andhra Pradesh dashboard page, archiving and continuing')
                        archive_raw_source(city,str(soup))
                        continue
                    else:
                        x=x[0]

                    (
                        # ~ xyz,
                        # ~ number_of_hospitals,
                        tot_icu,
                        occupied_icu,
                        vacant_icu,
                        tot_o2,
                        occupied_o2,
                        vacant_o2,
                        tot_normal,
                        occupied_normal,
                        vacant_normal,
                        # ~ tot_vent,
                        # ~ occupied_vent,
                        # ~ vacant_vent,
                    ) = list(x.iloc[len(x)-1])[3:12]
                    
                    tot_vent=occupied_vent=""
                    
                    row = (
                        date_str,
                        tot_normal,
                        tot_o2,
                        tot_icu,
                        tot_vent,
                        occupied_normal,
                        occupied_o2,
                        occupied_icu,
                        occupied_vent,
                    )
                    print(city + ":")
                    print(row)
                    archive_raw_source(city,str(soup))
                except:
                    print(
                        "Failed to download/scrape AP data from http://dashboard.covid19.ap.gov.in/ims/hospbed_reports/ !!"
                    )
            elif city == "telangana":

                soup = get_url_failsafe(
                    "http://164.100.112.24/SpringMVC/Hospital_Beds_Statistic_Bulletin_citizen.htm"
                )
                try:
                    (
                        xyz,
                        tot_normal,
                        occupied_normal,
                        vacant_normal,
                        tot_o2,
                        occupied_o2,
                        vacant_o2,
                        tot_icu,
                        occupied_icu,
                        vacant_icu,
                        a1,
                        a2,
                        a3,
                    ) = [i.text for i in soup("tr")[-1]("th")]
                except:
                    print(
                        "could not unpack "
                        + str([i.text for i in soup("tr")[-1]("th")])
                    )
                row = (
                    date_str,
                    tot_normal,
                    tot_o2,
                    tot_icu,
                    occupied_normal,
                    occupied_o2,
                    occupied_icu,
                )
                print(city + ":")
                print(row)
                archive_raw_source(city,str(soup))
            elif city == "kerala":

                soup = get_url_failsafe(
                    "https://covid19jagratha.kerala.nic.in/home/addHospitalDashBoard"
                )

                n = soup("div", attrs={"class": "box"})[1]
                vacant_normal, tot_normal = (
                    n("p")[0].text.replace(n("label")[0].text, "").strip().split("/")
                )

                n = soup("div", attrs={"class": "box"})[2]
                vacant_icu, tot_icu = (
                    n("p")[0].text.replace(n("label")[0].text, "").strip().split("/")
                )

                n = soup("div", attrs={"class": "box"})[3]
                vacant_vent, tot_vent = (
                    n("p")[0].text.replace(n("label")[0].text, "").strip().split("/")
                )

                n = soup("div", attrs={"class": "box"})[4]
                vacant_o2, tot_o2 = (
                    n("p")[0].text.replace(n("label")[0].text, "").strip().split("/")
                )
                occupied_normal=int(tot_normal)-int(vacant_normal)
                occupied_o2=int(tot_o2)-int(vacant_o2)
                occupied_icu=int(tot_icu)-int(vacant_icu)                
                occupied_vent=int(tot_vent)-int(vacant_vent)
                
                row = (
                    date_str,
                    tot_normal,
                    tot_o2,
                    tot_icu,
                    tot_vent,
                    occupied_normal,
                    occupied_o2,
                    occupied_icu,
                    occupied_vent,
                )
                print(city + ":")
                print(row)
                archive_raw_source(city,str(soup))

            elif city == "uttarakhand":

                soup = get_url_failsafe("https://covid19.uk.gov.in/bedssummary.aspx")

                n = soup("div", attrs={"id": "ContentPlaceHolder1_divIsolation"})[0]
                xz1, tot_normal, xz2, vacant_normal = [i.text for i in n("span")]
                occupied_normal = int(tot_normal) - int(vacant_normal)

                n = soup("div", attrs={"id": "ContentPlaceHolder1_divOx2"})[0]
                xz1, tot_o2, xz2, vacant_o2 = [i.text for i in n("span")]
                occupied_o2 = int(tot_o2) - int(vacant_o2)

                n = soup("div", attrs={"id": "ContentPlaceHolder1_divICU"})[0]
                xz1, tot_icu, xz2, vacant_icu = [i.text for i in n("span")]
                occupied_icu = int(tot_icu) - int(vacant_icu)

                n = soup("div", attrs={"id": "ContentPlaceHolder1_div1"})[0]
                xz1, tot_vent, xz2, vacant_vent = [i.text for i in n("span")]
                occupied_vent = int(tot_vent) - int(vacant_vent)

                row = (
                    date_str,
                    tot_normal,
                    tot_o2,
                    tot_icu,
                    tot_vent,
                    occupied_normal,
                    occupied_o2,
                    occupied_icu,
                    occupied_vent,
                )
                print(city + ":")
                print(row)
                archive_raw_source(city,str(soup))

            elif city == "chandigarh":

                soup = get_url_failsafe(
                    "http://chdcovid19.in/chdcovidbed19/index.php/home/stats"
                )
                table = soup("table")[0]

                # ~ toc=tvc=tic=tnc=0
                # ~ too=tvo=tio=tno=0
                # ~ for row in table('tr')[2:]:
                # ~ hospital_name,hosp_type,updated_on,oc,oa,ov,nc,no,nv,ic,io,iv,vc,vo,vv=[i.text for i in  row('td')]
                # ~ toc+=int(oc);        tvc+=int(vc);        tic+=int(ic);        tnc+=int(nc)
                # ~ too+=int(oo);        tvo+=int(vo);        tio+=int(io);        tno+=int(no)

                try:
                    xyz, toc, too, toa, tnc, tno, tna, tic, tio, tia, tvc, tvo, tva = [
                        i.text for i in table("tr")[-1]("td")
                    ]
                except:
                    print(
                        "could not unpack chandigarh values!\n"
                        + str(table("tr")[-1]("td"))
                    )
                row = (date_str, tnc, toc, tic, tvc, tno, too, tio, tvo)
                print(city + " : " + str(row))
                archive_raw_source(city,str(soup))
            elif city == "hp":

                soup = get_url_failsafe("https://covidcapacity.hp.gov.in/index.php")
                xx = soup("a", attrs={"id": "oxygenbedmodel"})[0]
                tot_o2 = int(xx.parent.parent("td")[0].text)
                occupied_o2 = int(xx.parent.parent("td")[1].text)
                xx = soup("a", attrs={"id": "icubedmodel"})[0]
                tot_icu = int(xx.parent.parent("td")[0].text)
                occupied_icu = int(xx.parent.parent("td")[1].text)
                xx = soup("a", attrs={"id": "Standardbedmodel"})[0]
                tot_normal = int(xx.parent.parent("td")[0].text)
                occupied_normal = int(xx.parent.parent("td")[1].text)
                row = (
                    date_str,
                    tot_normal,
                    tot_o2,
                    tot_icu,
                    occupied_normal,
                    occupied_o2,
                    occupied_icu,
                )
                print(city + ":")
                print(row)
                archive_raw_source(city,str(soup))
            elif city == "mp":

                soup = get_url_failsafe(
                    "http://sarthak.nhmmp.gov.in/covid/facility-bed-occupancy-dashboard/"
                )
                xx = soup(
                    "a",
                    attrs={
                        "href": "http://sarthak.nhmmp.gov.in/covid/facility-bed-occupancy-details"
                    },
                )
                (
                    tot_normal,
                    occupied_normal,
                    vacant_normal,
                    tot_o2,
                    occupied_o2,
                    vacant_o2,
                    tot_icu,
                    occupied_icu,
                    vacant_icu,
                ) = [i.text for i in xx if i.text.isnumeric()]
                row = (
                    date_str,
                    tot_normal,
                    tot_o2,
                    tot_icu,
                    occupied_normal,
                    occupied_o2,
                    occupied_icu,
                )
                print(city + ":")
                print(row)
                archive_raw_source(city,str(soup))
            elif city == "ludhiana":

                soup = get_url_failsafe("https://ludhiana.nic.in/bed-status/")
                links = soup.find_all("a")

                for link in links:
                    if ".pdf" in link.get("href", []):
                        print("Downloading pdf...")

                        l = link.get("href")
                        print(l)
                        response = requests.get(l)
                        pdf = open("LDH_" + str(date_str) + ".pdf", "wb")
                        pdf.write(response.content)
                        pdf.close()
                        break

                # get date
                os.system(
                    "pdftotext -f 1 -l 1 -x 0 -y 0 -W 500 -H 300  -layout LDH_"
                    + str(date_str)
                    + ".pdf tmp.txt"
                )
                b = [i.strip() for i in open("tmp.txt").readlines() if i.strip()]
                date_line = "Last edited on"
                if not b[3].startswith(date_line):
                    print(highlight("could not extract date for Ludhiana!!"))
                    continue
                date_line = b[3].split()
                date_line = date_line[date_line.index("on") + 1]
                bulletin_date = datetime.datetime.strptime(date_line, "%d-%B-%Y")

                # print(text)
                tables = read_pdf("LDH_" + str(date_str) + ".pdf", pages="all")
                df = tables[-1]
                nums = []
                for x in df.iloc[-1]:
                    if type(x) is None:
                        continue
                    if type(x) == str:
                        for s in x.split():
                            if s.isnumeric():
                                nums.append(s)

                # ~ print(nums)
                tot_o2, occupied_o2, vacant_o2, tot_icu, occupied_icu, vacant_icu = nums
                a = open("data.ludhiana.csv")
                r = csv.reader(a)
                info = [i for i in r]
                a.close()
                dates = list(set([i[0] for i in info[1:]]))
                dates.sort()
                # save space by deleting the pdf
                if os.path.exists("LDH_" + str(date_str) + ".pdf"):
                    os.remove("LDH_" + str(date_str) + ".pdf")
                date_str = bulletin_date.strftime("%Y-%m-%d")
                row = (date_str, tot_o2, tot_icu, occupied_o2, occupied_icu)
                print(city + ":" + str(row))
                # ~ if date_str in dates:
                # ~ print('----------\n\nData for %s already exists in data.ludhiana.csv!!\nOnly printing, not modifying csv!!\n\n----------\n\n' %(date_str))
                # ~ else:
                # ~ #write to file
                # ~ info=', '.join((date_str,tot_o2,tot_icu,occupied_o2,occupied_icu))
                # ~ print(city+' : '+str(info))
                # ~ # Date, L2_Total_Beds, L2_Occupied_Beds, L2_Available_Beds, L3_Total_Beds, L3_Occupied_Beds, L3_Available_Beds
                # ~ a=open('data.ludhiana.csv','a');a.write(info+'\n');a.close()
                # ~ print('Appended to data.ludhiana.csv: '+info)
            elif city == "chennai":
                # CHENNAI
                import requests
                from requests.structures import CaseInsensitiveDict

                url = "https://tncovidbeds.tnega.org/api/hospitals"

                headers = CaseInsensitiveDict()
                headers["authority"] = "tncovidbeds.tnega.org"
                # headers["sec-ch-ua"] = "" Not A;Brand";v="99", "Chromium";v="96", "Google Chrome";v="96""
                headers["dnt"] = "1"
                headers["sec-ch-ua-mobile"] = "?0"
                headers[
                    "user-agent"
                ] = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.45 Safari/537.36"
                headers["content-type"] = "application/json;charset=UTF-8"
                headers["accept"] = "application/json, text/plain, */*"
                headers["token"] = "null"
                # headers["sec-ch-ua-platform"] = ""Linux""
                headers["sec-ch-ua-platform"] = "Linux"
                headers["origin"] = "https://tncovidbeds.tnega.org"
                headers["sec-fetch-site"] = "same-origin"
                headers["sec-fetch-mode"] = "cors"
                headers["sec-fetch-dest"] = "empty"
                headers["accept-language"] = "en-US,en;q=0.9"
                # headers["cookie"] = "_ga=GA1.2.1493856265.1640076462; _gid=GA1.2.514620938.1640076462; _gat=1"

                data = '{"searchString":"","sortCondition":{"Name":1},"pageNumber":1,"pageLimit":200,"SortValue":"Availability","ShowIfVacantOnly":"","Districts":["5ea0abd2d43ec2250a483a40"],"BrowserId":"6f4dfda2b7835796132d69d0e8525127","IsGovernmentHospital":true,"IsPrivateHospital":true,"FacilityTypes":["CHO"]}'

                resp = requests.post(url, headers=headers, data=data)

                print(resp.status_code)
                y = json.loads(resp.content.decode("unicode_escape").replace("\n", ""))
                tot_o2_beds = 0
                tot_non_o2_beds = 0
                tot_icu_beds = 0
                occupied_o2_beds = 0
                occupied_non_o2_beds = 0
                occupied_icu_beds = 0
                vacant_o2_beds = 0
                vacant_non_o2_beds = 0
                vacant_icu_beds = 0

                for i in y["result"]:
                    tot_o2_beds += i["CovidBedDetails"]["AllotedO2Beds"]
                    tot_non_o2_beds += i["CovidBedDetails"]["AllotedNonO2Beds"]
                    tot_icu_beds += i["CovidBedDetails"]["AllotedICUBeds"]
                    occupied_o2_beds += i["CovidBedDetails"]["OccupancyO2Beds"]
                    occupied_non_o2_beds += i["CovidBedDetails"]["OccupancyNonO2Beds"]
                    occupied_icu_beds += i["CovidBedDetails"]["OccupancyICUBeds"]
                    vacant_o2_beds += i["CovidBedDetails"]["VaccantO2Beds"]
                    vacant_non_o2_beds += i["CovidBedDetails"]["VaccantNonO2Beds"]
                    vacant_icu_beds += i["CovidBedDetails"]["VaccantICUBeds"]
                print(
                    "In Chennai, on %s\nO2: %d/%d occupied\nNon-O2 %d/%d occupied\nICU: %d/%d occupied"
                    % (
                        date_str,
                        occupied_o2_beds,
                        tot_o2_beds,
                        occupied_non_o2_beds,
                        tot_non_o2_beds,
                        occupied_icu_beds,
                        tot_icu_beds,
                    )
                )

                a = open("data.chennai.csv")
                r = csv.reader(a)
                info = [i for i in r]
                a.close()
                dates = list(set([i[0] for i in info[1:]]))
                dates.sort()

                if date_str in dates:
                    # ~ dont_update_data_csv=True
                    print(
                        "----------\n\nData for %s already exists in data.chennai.csv!!\nOnly printing, not modifying csv!!\n\n----------\n\n"
                        % (date_str)
                    )
                else:
                    # write to file
                    info = ", ".join(
                        (
                            date_str,
                            str(tot_o2_beds),
                            str(tot_non_o2_beds),
                            str(tot_icu_beds),
                            str(occupied_o2_beds),
                            str(occupied_non_o2_beds),
                            str(occupied_icu_beds),
                        )
                    )
                    a = open("data.chennai.csv", "a")
                    a.write(info + "\n")
                    a.close()
                    print("Appended to data.chennai.csv: " + info)

            # generic writer for most cities
            if city in generic_writer_cities:
                csv_fname = "data." + city + ".csv"
                a = open(csv_fname)
                r = csv.reader(a)
                info = [i for i in r]
                a.close()
                dates = list(set([i[0] for i in info[1:]]))
                dates.sort()
                date_str = row[0]

                if date_str in dates:
                    # ~ dont_update_data_csv=True
                    print(
                        "----------\n\nData for %s already exists in %s!!\nOnly printing, not modifying csv!!\n\n----------\n\n"
                        % (date_str, csv_fname)
                    )
                else:
                    # write to file
                    a = open(csv_fname, "a")
                    w = csv.writer(a)
                    w.writerow(row)
                    a.close()
                    print("Appended to %s :%s" % (csv_fname, str(row)))
        except Exception as e:
            print(e)
            failed_cities.append(city)

    if failed_cities:
        detailed_date_str = datetime.datetime.now(
            tz=pytz.timezone("Asia/Kolkata")
        ).strftime("%Y-%m-%d %H:%M")
        print("Failed to run scraper for : " + ", ".join(failed_cities))
        afailed = open("failed_runs", "a")
        afailed.write(
            "On %s failed runs for: %s\n"
            % (detailed_date_str, ", ".join(failed_cities))
        )
        afailed.close()
    #commit raw sources
    os.system('git config --global user.email "you@example.com" && git config --global user.name "Your Name"&& git commit -a -m "adding raw sources" --verbose' )
