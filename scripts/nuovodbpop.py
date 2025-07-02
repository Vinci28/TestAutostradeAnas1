import os
import json
import re
import psycopg2
import pandas as pd
from datetime import datetime
from psycopg2.extras import execute_values

# === CONFIGURAZIONE CENTRALIZZATA ===
BASE_JSON_FOLDER = os.path.expanduser(r"E:\scarico_storico")
LOG_TABLE_NAME = "log_file_processati"
DB_CONFIG = {
    "dbname": "autostradeanasdb",
    "user": "vinc",
    "password": "1234",
    "host": "localhost",
    "port": 5432
}

# NUOVA STRUTTURA DI CONFIGURAZIONE PER LE STRADE
STRADE_CONFIG = {
    "SS675": {
        "table_name": "dati_storico_SS675",
        "punto_tratto_map": {"Punto_1": "SS675 Km 0+000_SS675 Km 1+040",
                             "Punto_2": "SS675 Km 1+040_SS675 Km 2+079",
                             "Punto_3": "SS675 Km 2+079_SS675 Km 3+115",
                             "Punto_4": "SS675 Km 3+115_SS675 Km 4+108",
                             "Punto_5": "SS675 Km 4+108_SS675 Km 5+033",
                             "Punto_6": "SS675 Km 5+033_SS675 Km 6+057",
                             "Punto_7": "SS675 Km 6+057_SS675 Km 7+062",
                             "Punto_8": "SS675 Km 7+062_SS675 Km 8+064",
                             "Punto_9": "SS675 Km 8+064_SS675 Km 9+064",
                             "Punto_10": "SS675 Km 9+064_SS675 Km 10+070",
                             "Punto_11": "SS675 Km 10+070_SS675 Km 11+067",
                             "Punto_12": "SS675 Km 11+067_SS675 Km 12+054",
                             "Punto_13": "SS675 Km 12+054_SS675 Km 13+042",
                             "Punto_14": "SS675 Km 13+042_SS675 Km 14+042",
                             "Punto_15": "SS675 Km 14+042_SS675 Km 15+048",
                             "Punto_16": "SS675 Km 15+048_SS675 Km 16+052",
                             "Punto_17": "SS675 Km 16+052_SS675 Km 17+056",
                             "Punto_18": "SS675 Km 17+056_SS675 Km 18+057",
                             "Punto_19": "SS675 Km 18+057_SS675 Km 19+036",
                             "Punto_20": "SS675 Km 19+036_SS675 Km 20+029",
                             "Punto_21": "SS675 Km 20+029_SS675 Km 21+034",
                             "Punto_22": "SS675 Km 21+034_SS675 Km 22+011",
                             "Punto_23": "SS675 Km 22+011_SS675 Km 23+026",
                             "Punto_24": "SS675 Km 23+026_SS675 Km 23+958",
                             "Punto_25": "SS675 Km 23+958_SS675 Km 24+955",
                             "Punto_26": "SS675 Km 24+955_SS675 Km 25+955",
                             "Punto_27": "SS675 Km 25+955_SS675 Km 26+958",
                             "Punto_28": "SS675 Km 26+958_SS675 Km 27+962",
                             "Punto_29": "SS675 Km 27+962_SS675 Km 28+939",
                             "Punto_30": "SS675 Km 28+939_SS675 Km 29+962",
                             "Punto_31": "SS675 Km 29+962_SS675 Km 30+974",
                             "Punto_32": "SS675 Km 30+974_SS675 Km 31+974",
                             "Punto_33": "SS675 Km 31+974_SS675 Km 32+980",
                             "Punto_34": "SS675 Km 32+980_SS675 Km 33+981",
                             "Punto_35": "SS675 Km 33+981_SS675 Km 34+985",
                             "Punto_36": "SS675 Km 34+985_SS675 Km 35+987",
                             "Punto_37": "SS675 Km 35+987_SS675 Km 37+001",
                             "Punto_38": "SS675 Km 37+001_SS675 Km 37+997",
                             "Punto_39": "SS675 Km 37+997_SS675 Km 39+000",
                             "Punto_40": "SS675 Km 39+000_SS675 Km 40+003",
                             "Punto_41": "SS675 Km 40+003_SS675 Km 41+006",
                             "Punto_42": "SS675 Km 41+006_SS675 Km 42+008",
                             "Punto_43": "SS675 Km 42+008_SS675 Km 43+009",
                             "Punto_44": "SS675 Km 43+009_SS675 Km 44+012",
                             "Punto_45": "SS675 Km 44+012_SS675 Km 45+014",
                             "Punto_46": "SS675 Km 45+014_SS675 Km 46+015",
                             "Punto_47": "SS675 Km 46+015_SS675 Km 47+017",
                             "Punto_48": "SS675 Km 47+017_SS675 Km 48+020",
                             "Punto_49": "SS675 Km 48+020_SS675 Km 49+024",
                             "Punto_50": "SS675 Km 49+024_SS675 Km 50+027",
                             "Punto_51": "SS675 Km 50+027_SS675 Km 51+030",
                             "Punto_52": "SS675 Km 51+030_SS675 Km 52+032",
                             "Punto_53": "SS675 Km 52+032_SS675 Km 53+036",
                             "Punto_54": "SS675 Km 53+036_SS675 Km 54+037",
                             "Punto_55": "SS675 Km 54+037_SS675 Km 55+039",
                             "Punto_56": "SS675 Km 55+039_SS675 Km 56+042",
                             "Punto_57": "SS675 Km 56+042_SS675 Km 57+046",
                             "Punto_58": "SS675 Km 57+046_SS675 Km 58+040",
                             "Punto_59": "SS675 Km 58+040_SS675 Km 59+050",
                             "Punto_60": "SS675 Km 59+050_SS675 Km 60+045",
                             "Punto_61": "SS675 Km 60+045_SS675 Km 61+033",
                             "Punto_62": "SS675 Km 61+033_SS675 Km 62+028",
                             "Punto_63": "SS675 Km 62+028_SS675 Km 63+028",
                             "Punto_64": "SS675 Km 63+028_SS675 Km 64+017",
                             "Punto_65": "SS675 Km 64+017_SS675 Km 65+014",
                             "Punto_66": "SS675 Km 65+014_SS675 Km 66+009",
                             "Punto_67": "SS675 Km 66+009_SS675 Km 67+003",
                             "Punto_68": "SS675 Km 67+003_SS675 Km 68+000",
                             "Punto_69": "SS675 Km 68+000_SS675 Km 68+999",
                             "Punto_70": "SS675 Km 68+999_SS675 Km 69+996",
                             "Punto_71": "SS675 Km 69+996_SS675 Km 70+995",
                             "Punto_72": "SS675 Km 70+995_SS675 Km 71+993",
                             "Punto_73": "SS675 Km 71+993_SS675 Km 72+990",
                             "Punto_74": "SS675 Km 72+990_SS675 Km 73+981",
                             "Punto_75": "SS675 Km 73+981_SS675 Km 74+976",
                             "Punto_76": "SS675 Km 74+976_SS675 Km 75+972",
                             "Punto_77": "SS675 Km 75+972_SS675 Km 76+967",
                             "Punto_78": "SS675 Km 76+967_SS675 Km 77+963",
                             "Punto_79": "SS675 Km 77+963_SS675 Km 78+966",
                             "Punto_80": "SS675 Km 78+966_SS675 Km 79+972",
                             "Punto_81": "SS675 Km 79+972_SS675 Km 80+975",
                             "Punto_82": "SS675 Km 80+975_SS675 Km 81+979",
                             "Punto_83": "SS675 Km 81+979_SS675 Km 82+978",
                             "Punto_84": "SS675 Km 82+978_SS675 Km 83+976",
                             "Punto_85": "SS675 Km 83+976_SS675 Km 84+979",
                             "Punto_86": "SS675 Km 84+979_SS675 Km 85+116"}
    },
    "A90": {
        "table_name": "dati_storico_A90",
        "punto_tratto_map": {
            "Punto_1": "A90 Km 0+000_A90 Km 0+996",
            "Punto_2": "A90 Km 0+996_A90 Km 1+982",
            "Punto_3": "A90 Km 1+982_A90 Km 2+963",
            "Punto_4": "A90 Km 2+963_A90 Km 3+951",
            "Punto_5": "A90 Km 3+951_A90 Km 4+955",
            "Punto_6": "A90 Km 4+955_A90 Km 5+992",
            "Punto_7": "A90 Km 5+992_A90 Km 7+007",
            "Punto_8": "A90 Km 7+007_A90 Km 8+023",
            "Punto_9": "A90 Km 8+023_A90 Km 9+054",
            "Punto_10": "A90 Km 9+054_A90 Km 10+057",
            "Punto_11": "A90 Km 10+057_A90 Km 11+068",
            "Punto_12": "A90 Km 11+068_A90 Km 12+067",
            "Punto_13": "A90 Km 12+067_A90 Km 12+908",
            "Punto_14": "A90 Km 12+908_A90 Km 13+905",
            "Punto_15": "A90 Km 13+905_A90 Km 14+931",
            "Punto_16": "A90 Km 14+931_A90 Km 15+950",
            "Punto_17": "A90 Km 15+950_A90 Km 16+984",
            "Punto_18": "A90 Km 16+984_A90 Km 18+017",
            "Punto_19": "A90 Km 18+017_A90 Km 19+038",
            "Punto_20": "A90 Km 19+038_A90 Km 20+062",
            "Punto_21": "A90 Km 20+062_A90 Km 21+069",
            "Punto_22": "A90 Km 21+069_A90 Km 22+076",
            "Punto_23": "A90 Km 22+076_A90 Km 23+082",
            "Punto_24": "A90 Km 23+082_A90 Km 24+088",
            "Punto_25": "A90 Km 24+088_A90 Km 25+099",
            "Punto_26": "A90 Km 25+099_A90 Km 26+105",
            "Punto_27": "A90 Km 26+105_A90 Km 27+107",
            "Punto_28": "A90 Km 27+107_A90 Km 28+103",
            "Punto_29": "A90 Km 28+103_A90 Km 29+112",
            "Punto_30": "A90 Km 29+112_A90 Km 30+114",
            "Punto_31": "A90 Km 30+114_A90 Km 31+120",
            "Punto_32": "A90 Km 31+120_A90 Km 32+119",
            "Punto_33": "A90 Km 32+119_A90 Km 33+122",
            "Punto_34": "A90 Km 33+122_A90 Km 34+115",
            "Punto_35": "A90 Km 34+115_A90 Km 35+109",
            "Punto_36": "A90 Km 35+109_A90 Km 36+119",
            "Punto_37": "A90 Km 36+119_A90 Km 37+124",
            "Punto_38": "A90 Km 37+124_A90 Km 38+128",
            "Punto_39": "A90 Km 38+128_A90 Km 39+131",
            "Punto_40": "A90 Km 39+131_A90 Km 40+137",
            "Punto_41": "A90 Km 40+137_A90 Km 41+130",
            "Punto_42": "A90 Km 41+130_A90 Km 42+135",
            "Punto_43": "A90 Km 42+135_A90 Km 43+079",
            "Punto_44": "A90 Km 43+079_A90 Km 44+089",
            "Punto_45": "A90 Km 44+089_A90 Km 45+121",
            "Punto_46": "A90 Km 45+121_A90 Km 46+135",
            "Punto_47": "A90 Km 46+135_A90 Km 47+112",
            "Punto_48": "A90 Km 47+112_A90 Km 48+119",
            "Punto_49": "A90 Km 48+119_A90 Km 49+128",
            "Punto_50": "A90 Km 49+128_A90 Km 50+137",
            "Punto_51": "A90 Km 50+137_A90 Km 51+143",
            "Punto_52": "A90 Km 51+143_A90 Km 52+142",
            "Punto_53": "A90 Km 52+142_A90 Km 53+145",
            "Punto_54": "A90 Km 53+145_A90 Km 54+152",
            "Punto_55": "A90 Km 54+152_A90 Km 55+161",
            "Punto_56": "A90 Km 55+161_A90 Km 56+164",
            "Punto_57": "A90 Km 56+164_A90 Km 57+171",
            "Punto_58": "A90 Km 57+171_A90 Km 58+161",
            "Punto_59": "A90 Km 58+161_A90 Km 59+170",
            "Punto_60": "A90 Km 59+170_A90 Km 60+180",
            "Punto_61": "A90 Km 60+180_A90 Km 61+186",
            "Punto_62": "A90 Km 61+186_A90 Km 62+188",
            "Punto_63": "A90 Km 62+188_A90 Km 63+195",
            "Punto_64": "A90 Km 63+195_A90 Km 64+199",
            "Punto_65": "A90 Km 64+199_A90 Km 65+208",
            "Punto_66": "A90 Km 65+208_A90 Km 66+220",
            "Punto_67": "A90 Km 66+220_A90 Km 67+235",
            "Punto_68": "A90 Km 67+235_A90 Km 68+236",
            "Punto_69": "A90 Km 68+236_A90 Km 68+040"
        }
    },
    "SS51": {
        "table_name": "dati_storico_SS51",
        "punto_tratto_map": {
            "Punto_1": "SS51 Km 0+000_SS51 Km 0+778",
            "Punto_2": "SS51 Km 0+778_SS51 Km 1+693",
            "Punto_3": "SS51 Km 1+693_SS51 Km 2+684",
            "Punto_4": "SS51 Km 2+684_SS51 Km 3+687",
            "Punto_5": "SS51 Km 3+687_SS51 Km 4+677",
            "Punto_6": "SS51 Km 4+677_SS51 Km 5+672",
            "Punto_7": "SS51 Km 5+672_SS51 Km 7+000",
            "Punto_8": "SS51 Km 7+000_SS51 Km 8+000",
            "Punto_9": "SS51 Km 8+000_SS51 Km 9+000",
            "Punto_10": "SS51 Km 9+000_SS51 Km 10+000",
            "Punto_11": "SS51 Km 10+000_SS51 Km 11+000",
            "Punto_12": "SS51 Km 11+000_SS51 Km 12+000",
            "Punto_13": "SS51 Km 12+000_SS51 Km 13+000",
            "Punto_14": "SS51 Km 13+000_SS51 Km 13+774",
            "Punto_15": "SS51 Km 13+774_SS51 Km 14+782",
            "Punto_16": "SS51 Km 14+782_SS51 Km 15+791",
            "Punto_17": "SS51 Km 15+791_SS51 Km 16+797",
            "Punto_18": "SS51 Km 16+797_SS51 Km 17+826",
            "Punto_19": "SS51 Km 17+826_SS51 Km 18+973",
            "Punto_20": "SS51 Km 18+973_SS51 Km 19+972",
            "Punto_21": "SS51 Km 19+972_SS51 Km 20+972",
            "Punto_22": "SS51 Km 20+972_SS51 Km 21+979",
            "Punto_23": "SS51 Km 21+979_SS51 Km 22+984",
            "Punto_24": "SS51 Km 22+984_SS51 Km 23+988",
            "Punto_25": "SS51 Km 23+988_SS51 Km 25+019",
            "Punto_26": "SS51 Km 25+019_SS51 Km 26+026",
            "Punto_27": "SS51 Km 26+026_SS51 Km 27+043",
            "Punto_28": "SS51 Km 27+043_SS51 Km 28+055",
            "Punto_29": "SS51 Km 28+055_SS51 Km 29+056",
            "Punto_30": "SS51 Km 29+056_SS51 Km 30+064",
            "Punto_31": "SS51 Km 30+064_SS51 Km 31+073",
            "Punto_32": "SS51 Km 31+073_SS51 Km 32+082",
            "Punto_33": "SS51 Km 32+082_SS51 Km 33+093",
            "Punto_34": "SS51 Km 33+093_SS51 Km 34+100",
            "Punto_35": "SS51 Km 34+100_SS51 Km 35+102",
            "Punto_36": "SS51 Km 35+102_SS51 Km 36+046",
            "Punto_37": "SS51 Km 36+046_SS51 Km 37+060",
            "Punto_38": "SS51 Km 37+060_SS51 Km 38+070",
            "Punto_39": "SS51 Km 38+070_SS51 Km 39+092",
            "Punto_40": "SS51 Km 39+092_SS51 Km 40+110",
            "Punto_41": "SS51 Km 40+110_SS51 Km 41+153",
            "Punto_42": "SS51 Km 41+153_SS51 Km 42+165",
            "Punto_43": "SS51 Km 42+165_SS51 Km 43+232",
            "Punto_44": "SS51 Km 43+232_SS51 Km 44+263",
            "Punto_45": "SS51 Km 44+263_SS51 Km 45+295",
            "Punto_46": "SS51 Km 45+295_SS51 Km 46+331",
            "Punto_47": "SS51 Km 46+331_SS51 Km 47+372",
            "Punto_48": "SS51 Km 47+372_SS51 Km 48+414",
            "Punto_49": "SS51 Km 48+414_SS51 Km 49+451",
            "Punto_50": "SS51 Km 49+451_SS51 Km 50+500",
            "Punto_51": "SS51 Km 50+500_SS51 Km 51+523",
            "Punto_52": "SS51 Km 51+523_SS51 Km 52+520",
            "Punto_53": "SS51 Km 52+520_SS51 Km 53+526",
            "Punto_54": "SS51 Km 53+526_SS51 Km 54+529",
            "Punto_55": "SS51 Km 54+529_SS51 Km 55+532",
            "Punto_56": "SS51 Km 55+532_SS51 Km 56+542",
            "Punto_57": "SS51 Km 56+542_SS51 Km 57+641",
            "Punto_58": "SS51 Km 57+641_SS51 Km 58+808",
            "Punto_59": "SS51 Km 58+808_SS51 Km 59+976",
            "Punto_60": "SS51 Km 59+976_SS51 Km 61+155",
            "Punto_61": "SS51 Km 61+155_SS51 Km 62+346",
            "Punto_62": "SS51 Km 62+346_SS51 Km 63+512",
            "Punto_63": "SS51 Km 63+512_SS51 Km 64+577",
            "Punto_64": "SS51 Km 64+577_SS51 Km 65+580",
            "Punto_65": "SS51 Km 65+580_SS51 Km 66+591",
            "Punto_66": "SS51 Km 66+591_SS51 Km 67+595",
            "Punto_67": "SS51 Km 67+595_SS51 Km 68+593",
            "Punto_68": "SS51 Km 68+593_SS51 Km 71+369",
            "Punto_69": "SS51 Km 71+369_SS51 Km 72+815",
            "Punto_70": "SS51 Km 72+815_SS51 Km 73+820",
            "Punto_71": "SS51 Km 73+820_SS51 Km 74+818",
            "Punto_72": "SS51 Km 74+818_SS51 Km 75+826",
            "Punto_73": "SS51 Km 75+826_SS51 Km 76+829",
            "Punto_74": "SS51 Km 76+829_SS51 Km 77+873",
            "Punto_75": "SS51 Km 77+873_SS51 Km 78+849",
            "Punto_76": "SS51 Km 78+849_SS51 Km 79+855",
            "Punto_77": "SS51 Km 79+855_SS51 Km 80+863",
            "Punto_78": "SS51 Km 80+863_SS51 Km 81+872",
            "Punto_79": "SS51 Km 81+872_SS51 Km 82+889",
            "Punto_80": "SS51 Km 82+889_SS51 Km 83+896",
            "Punto_81": "SS51 Km 83+896_SS51 Km 84+900",
            "Punto_82": "SS51 Km 84+900_SS51 Km 85+901",
            "Punto_83": "SS51 Km 85+901_SS51 Km 86+894",
            "Punto_84": "SS51 Km 86+894_SS51 Km 87+918",
            "Punto_85": "SS51 Km 87+918_SS51 Km 88+928",
            "Punto_86": "SS51 Km 88+928_SS51 Km 89+948",
            "Punto_87": "SS51 Km 89+948_SS51 Km 90+935",
            "Punto_88": "SS51 Km 90+935_SS51 Km 91+948",
            "Punto_89": "SS51 Km 91+948_SS51 Km 92+994",
            "Punto_90": "SS51 Km 92+994_SS51 Km 93+998",
            "Punto_91": "SS51 Km 93+998_SS51 Km 94+996",
            "Punto_92": "SS51 Km 94+996_SS51 Km 96+097",
            "Punto_93": "SS51 Km 96+097_SS51 Km 97+093",
            "Punto_94": "SS51 Km 97+093_SS51 Km 98+112",
            "Punto_95": "SS51 Km 98+112_SS51 Km 99+123",
            "Punto_96": "SS51 Km 99+123_SS51 Km 100+144",
            "Punto_97": "SS51 Km 100+144_SS51 Km 101+151",
            "Punto_98": "SS51 Km 101+151_SS51 Km 102+153",
            "Punto_99": "SS51 Km 102+153_SS51 Km 103+050",
            "Punto_100": "SS51 Km 103+050_SS51 Km 103+948",
            "Punto_101": "SS51 Km 103+948_SS51 Km 104+948",
            "Punto_102": "SS51 Km 104+948_SS51 Km 105+951",
            "Punto_103": "SS51 Km 105+951_SS51 Km 106+973",
            "Punto_104": "SS51 Km 106+973_SS51 Km 107+982",
            "Punto_105": "SS51 Km 107+982_SS51 Km 108+991",
            "Punto_106": "SS51 Km 108+991_SS51 Km 109+967",
            "Punto_107": "SS51 Km 109+967_SS51 Km 110+995",
            "Punto_108": "SS51 Km 110+995_SS51 Km 112+018",
            "Punto_109": "SS51 Km 112+018_SS51 Km 113+030",
            "Punto_110": "SS51 Km 113+030_SS51 Km 114+031",
            "Punto_111": "SS51 Km 114+031_SS51 Km 115+036",
            "Punto_112": "SS51 Km 115+036_SS51 Km 116+041",
            "Punto_113": "SS51 Km 116+041_SS51 Km 117+040",
            "Punto_114": "SS51 Km 117+040_SS51 Km 118+047",
            "Punto_115": "SS51 Km 118+047_SS51 Km 118+256"
        }
    }
}

CAMPI_INTERESSE = ["precipitation", "precipitation_probability", "precipitation_hours", "convective_precipitation",
                   "snowfraction", "temperature", "windspeed", "winddirection", "rainspot", "predictability",
                   "predictability_class"]


def crea_tabelle(conn):
    """Crea le tabelle dati per ogni strada e la tabella di log se non esistono."""
    with conn.cursor() as cur:
        for config in STRADE_CONFIG.values():
            table_name = config['table_name']
            cur.execute(f"""
                CREATE TABLE IF NOT EXISTS {table_name} (
                    downloaded_at TIMESTAMP, tratto TEXT, punto TEXT, time TIMESTAMP,
                    precipitation REAL, precipitation_probability REAL, precipitation_hours REAL,
                    convective_precipitation REAL, snowfraction REAL, temperature REAL,
                    windspeed REAL, winddirection REAL, rainspot TEXT, predictability REAL,
                    predictability_class REAL,
                    UNIQUE (punto, time)
                );
            """)
            print(f"Tabella '{table_name}' verificata/creata.")

        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS {LOG_TABLE_NAME} (
                filename TEXT PRIMARY KEY,
                processed_at TIMESTAMP DEFAULT NOW()
            );
        """)
        print(f"Tabella '{LOG_TABLE_NAME}' verificata/creata.")
        conn.commit()


def get_processed_files(conn):
    with conn.cursor() as cur:
        cur.execute(f"SELECT filename FROM {LOG_TABLE_NAME};")
        return {row[0] for row in cur.fetchall()}


def inserisci_dati_e_log(conn, df, filename, table_name):
    with conn.cursor() as cur:
        columns = df.columns.tolist()
        data_tuples = [tuple(row) for row in df.to_numpy()]
        insert_query = f"INSERT INTO {table_name} ({', '.join(columns)}) VALUES %s ON CONFLICT (punto, time) DO NOTHING;"
        execute_values(cur, insert_query, data_tuples)
        log_query = f"INSERT INTO {LOG_TABLE_NAME} (filename) VALUES (%s);"
        cur.execute(log_query, (filename,))
        print(f"  -> OK: Dati dal file '{filename}' inseriti in '{table_name}' e loggati.")


def extract_timestamp_from_filename(filename):
    match = re.search(r"(\d{4}-\d{2}-\d{2}_\d{2}-\d{2})", filename)
    if match:
        try:
            return datetime.strptime(match.group(1), "%Y-%m-%d_%H-%M")
        except ValueError:
            pass
    return None


def extract_punto_from_filename(filename):
    match = re.search(r"(Punto_\d+)", filename)
    return match.group(1) if match else None


def main():
    conn = None
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        crea_tabelle(conn)
        processed_files = get_processed_files(conn)
        print(f"Trovati {len(processed_files)} file già nel database.")

        for strada_nome, config in STRADE_CONFIG.items():
            table_name = config['table_name']
            punto_tratto_map = config['punto_tratto_map']
            json_folder_path = os.path.join(BASE_JSON_FOLDER, strada_nome)

            print(f"\n--- Inizio elaborazione per la strada: {strada_nome} ---")
            print(f"Cartella: {json_folder_path} | Tabella di destinazione: {table_name}")

            if not os.path.isdir(json_folder_path):
                print(f"[ATTENZIONE] La cartella non esiste, la salto: {json_folder_path}")
                continue

            files_in_folder = [f for f in os.listdir(json_folder_path) if f.endswith(".json")]
            nuovi_file_per_strada = 0

            for filename in files_in_folder:
                if filename in processed_files:
                    continue

                nuovi_file_per_strada += 1
                print(f"Elaboro il file: {filename}...")
                filepath = os.path.join(json_folder_path, filename)

                punto = extract_punto_from_filename(filename)
                tratto = punto_tratto_map.get(punto)
                timestamp_file = extract_timestamp_from_filename(filename)

                if not all([punto, tratto, timestamp_file]):
                    print(f"[AVVISO] Metadati mancanti o tratto non mappato per {punto} in {filename}. Salto.")
                    continue
                try:
                    with open(filepath, "r") as f:
                        data = json.load(f)
                except json.JSONDecodeError:
                    print(f"[ERRORE] File JSON non valido: {filename}. Salto.")
                    continue

                # --- MODIFICA INIZIO: Logica per estrarre la data del giorno di riferimento ---
                model_run_date = None
                try:
                    model_run_str = data.get("metadata", {}).get("modelrun_updatetime_utc")
                    if model_run_str:
                        # Estrae solo la parte della data (YYYY-MM-DD) e la converte
                        model_run_date = datetime.strptime(model_run_str.split(" ")[0], "%Y-%m-%d").date()
                    else:
                        print(
                            f"[AVVISO] 'modelrun_updatetime_utc' non trovato in {filename}. Il filtro giornaliero non sarà applicato.")
                except (ValueError, KeyError, IndexError):
                    print(
                        f"[AVVISO] Formato data in 'modelrun_updatetime_utc' non valido in {filename}. Il filtro non sarà applicato.")
                # --- MODIFICA FINE ---

                time_list = data.get("data_1h", {}).get("time", [])
                if not time_list:
                    print(f"[AVVISO] Nessun dato orario in: {filename}. Salto.")
                    continue

                rows = []
                for i, time_str in enumerate(time_list):
                    row = {"downloaded_at": timestamp_file.replace(microsecond=0), "tratto": tratto, "punto": punto,
                           "time": datetime.strptime(time_str, "%Y-%m-%d %H:%M").replace(microsecond=0)}
                    for campo in CAMPI_INTERESSE:
                        # La logica originale per popolare i campi rimane invariata
                        if campo in ["precipitation_hours", "predictability", "predictability_class"]:
                            row[campo] = None
                        elif campo in data.get("data_1h", {}):
                            if i < len(data["data_1h"][campo]):
                                row[campo] = data["data_1h"][campo][i]
                            else:
                                row[campo] = None
                        else:
                            row[campo] = None
                    rows.append(row)

                if "data_day" in data and data["data_day"] is not None:
                    # La logica originale per arricchire con data_day rimane invariata
                    for j, day in enumerate(data["data_day"].get("time", [])):
                        start_idx = data["data_day"]["indexto1hvalues_start"][j]
                        end_idx = data["data_day"]["indexto1hvalues_end"][j] + 1
                        for idx in range(start_idx, end_idx):
                            if idx < len(rows):
                                rows[idx]["precipitation_hours"] = data["data_day"]["precipitation_hours"][j]
                                rows[idx]["predictability"] = data["data_day"]["predictability"][j]
                                rows[idx]["predictability_class"] = data["data_day"]["predictability_class"][j]

                # --- MODIFICA INIZIO: Filtra i dati per mantenere solo quelli del giorno di riferimento ---
                if model_run_date:
                    original_row_count = len(rows)
                    # Crea una nuova lista contenente solo le righe la cui data corrisponde a model_run_date
                    filtered_rows = [row for row in rows if row['time'].date() == model_run_date]

                    if not filtered_rows:
                        print(
                            f"  -> [AVVISO] Nessun dato orario per il giorno {model_run_date} trovato in {filename}. File saltato.")
                        continue  # Salta al prossimo file se non ci sono dati per quel giorno

                    print(
                        f"  -> Filtrati {len(filtered_rows)} record su {original_row_count} per la data {model_run_date}.")
                    rows = filtered_rows  # Sostituisce la lista completa con quella filtrata
                # --- MODIFICA FINE ---

                df = pd.DataFrame(rows)
                if df.empty:
                    print(f"  -> [AVVISO] DataFrame vuoto dopo il processo di filtraggio per {filename}. File saltato.")
                    continue

                inserisci_dati_e_log(conn, df, filename, table_name)
                conn.commit()

            if nuovi_file_per_strada == 0:
                print(f"Nessun nuovo file da processare per {strada_nome}.")

    except (Exception, psycopg2.DatabaseError) as error:
        print(f"ERRORE GRAVE DURANTE L'ESECUZIONE: {error}")
        if conn: conn.rollback()
    finally:
        if conn: conn.close()
        print("\nElaborazione di tutte le strade completata.")


if __name__ == "__main__":
    main()