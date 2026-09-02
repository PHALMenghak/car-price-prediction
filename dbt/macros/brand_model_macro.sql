-- dbt/macros/brand_model_macro.sql
-- Resolves vehicle brand and canonical vehicle model using SQL regex rules for DuckDB.

{% macro extract_brand_from_raw(raw_brand_col, title_col) %}
    CASE
        -- 1. Trust clean explicit raw brand if known
        WHEN {{ raw_brand_col }} IS NOT NULL AND {{ raw_brand_col }} NOT IN ('', 'Unknown', 'None', 'nan', 'other') THEN
            CASE
                WHEN LOWER({{ raw_brand_col }}) LIKE '%toyota%' OR {{ raw_brand_col }} LIKE '%តូយ៉ូតា%' THEN 'Toyota'
                WHEN LOWER({{ raw_brand_col }}) LIKE '%lexus%' OR {{ raw_brand_col }} LIKE '%ឡិចស៊ីស%' THEN 'Lexus'
                WHEN LOWER({{ raw_brand_col }}) LIKE '%mercedes%' OR LOWER({{ raw_brand_col }}) LIKE '%benz%' THEN 'Mercedes-Benz'
                WHEN LOWER({{ raw_brand_col }}) LIKE '%land rover%' OR LOWER({{ raw_brand_col }}) LIKE '%range rover%' THEN 'Land Rover'
                WHEN LOWER({{ raw_brand_col }}) LIKE '%ford%' OR {{ raw_brand_col }} LIKE '%ហ្វត%' THEN 'Ford'
                WHEN LOWER({{ raw_brand_col }}) LIKE '%hyundai%' OR {{ raw_brand_col }} LIKE '%ហ៊ីយ៉ាន់ដាយ%' THEN 'Hyundai'
                WHEN LOWER({{ raw_brand_col }}) LIKE '%kia%' OR {{ raw_brand_col }} LIKE '%គា%' THEN 'Kia'
                WHEN LOWER({{ raw_brand_col }}) LIKE '%bmw%' OR {{ raw_brand_col }} LIKE '%ប៊ីអឹម%' THEN 'BMW'
                WHEN LOWER({{ raw_brand_col }}) LIKE '%mazda%' OR {{ raw_brand_col }} LIKE '%ម៉ាសដា%' THEN 'Mazda'
                WHEN LOWER({{ raw_brand_col }}) LIKE '%mitsubishi%' OR {{ raw_brand_col }} LIKE '%មីស៊ូប៊ីស៊ី%' THEN 'Mitsubishi'
                WHEN LOWER({{ raw_brand_col }}) LIKE '%nissan%' OR {{ raw_brand_col }} LIKE '%នីសាន់%' THEN 'Nissan'
                WHEN LOWER({{ raw_brand_col }}) LIKE '%byd%' THEN 'BYD'
                WHEN LOWER({{ raw_brand_col }}) LIKE '%avatr%' OR LOWER({{ raw_brand_col }}) LIKE '%avita%' THEN 'AVATR'
                WHEN LOWER({{ raw_brand_col }}) LIKE '%changan%' THEN 'Changan'
                WHEN LOWER({{ raw_brand_col }}) LIKE '%geely%' THEN 'Geely'
                WHEN LOWER({{ raw_brand_col }}) LIKE '%mg%' THEN 'MG'
                WHEN LOWER({{ raw_brand_col }}) LIKE '%honda%' OR {{ raw_brand_col }} LIKE '%ហុងដា%' THEN 'Honda'
                WHEN LOWER({{ raw_brand_col }}) LIKE '%isuzu%' OR {{ raw_brand_col }} LIKE '%អ៊ីស៊ូហ្ស៊ុ%' THEN 'Isuzu'
                WHEN LOWER({{ raw_brand_col }}) LIKE '%suzuki%' OR {{ raw_brand_col }} LIKE '%ស៊ុយស៊ូគី%' THEN 'Suzuki'
                WHEN LOWER({{ raw_brand_col }}) LIKE '%subaru%' THEN 'Subaru'
                WHEN LOWER({{ raw_brand_col }}) LIKE '%chevrolet%' OR LOWER({{ raw_brand_col }}) LIKE '%chevy%' THEN 'Chevrolet'
                WHEN LOWER({{ raw_brand_col }}) LIKE '%volkswagen%' OR LOWER({{ raw_brand_col }}) LIKE '%vw%' THEN 'Volkswagen'
                WHEN LOWER({{ raw_brand_col }}) LIKE '%porsche%' THEN 'Porsche'
                WHEN LOWER({{ raw_brand_col }}) LIKE '%audi%' THEN 'Audi'
                WHEN LOWER({{ raw_brand_col }}) LIKE '%volvo%' THEN 'Volvo'
                WHEN LOWER({{ raw_brand_col }}) LIKE '%cadillac%' THEN 'Cadillac'
                WHEN LOWER({{ raw_brand_col }}) LIKE '%jeep%' THEN 'Jeep'
                WHEN LOWER({{ raw_brand_col }}) LIKE '%dodge%' THEN 'Dodge'
                WHEN LOWER({{ raw_brand_col }}) LIKE '%rolls-royce%' OR LOWER({{ raw_brand_col }}) LIKE '%rolls royce%' THEN 'Rolls-Royce'
                ELSE {{ raw_brand_col }}
            END

        -- 2. Fallback to title regex extraction
        WHEN REGEXP_MATCHES(LOWER({{ title_col }}), 'mercedes[- ]benz|mercedes|\bbenz\b|\bamg\b|\bbrabus\b|មែរសឺដេស') THEN 'Mercedes-Benz'
        WHEN REGEXP_MATCHES(LOWER({{ title_col }}), 'land[- ]rover|range[- ]rover|rang[- ]rover|\brr\s+sport\b|\brr\b') THEN 'Land Rover'
        WHEN REGEXP_MATCHES(LOWER({{ title_col }}), 'rolls[- ]royce') THEN 'Rolls-Royce'
        WHEN REGEXP_MATCHES(LOWER({{ title_col }}), 'aston[- ]martin') THEN 'Aston Martin'
        WHEN REGEXP_MATCHES(LOWER({{ title_col }}), 'alfa[- ]romeo') THEN 'Alfa Romeo'
        WHEN REGEXP_MATCHES(LOWER({{ title_col }}), 'great[- ]wall') THEN 'Great Wall'
        WHEN REGEXP_MATCHES(LOWER({{ title_col }}), 'vinfast') THEN 'VinFast'
        WHEN REGEXP_MATCHES(LOWER({{ title_col }}), 'avatr|avita') THEN 'AVATR'
        WHEN REGEXP_MATCHES(LOWER({{ title_col }}), 'toyota|តូយ៉ូតា') THEN 'Toyota'
        WHEN REGEXP_MATCHES(LOWER({{ title_col }}), 'lexus|ឡិចស៊ីស') THEN 'Lexus'
        WHEN REGEXP_MATCHES(LOWER({{ title_col }}), 'ford|ហ្វត') THEN 'Ford'
        WHEN REGEXP_MATCHES(LOWER({{ title_col }}), 'honda|ហុងដា') THEN 'Honda'
        WHEN REGEXP_MATCHES(LOWER({{ title_col }}), '\bbmw\b|ប៊ីអឹម') THEN 'BMW'
        WHEN REGEXP_MATCHES(LOWER({{ title_col }}), 'hyundai|ហ៊ីយ៉ាន់ដាយ') THEN 'Hyundai'
        WHEN REGEXP_MATCHES(LOWER({{ title_col }}), '\bkia\b|គា\b|起亚') THEN 'Kia'
        WHEN REGEXP_MATCHES(LOWER({{ title_col }}), 'mazda|ម៉ាសដា') THEN 'Mazda'
        WHEN REGEXP_MATCHES(LOWER({{ title_col }}), 'mitsubishi|មីស៊ូប៊ីស៊ី') THEN 'Mitsubishi'
        WHEN REGEXP_MATCHES(LOWER({{ title_col }}), 'nissan|នីសាន់') THEN 'Nissan'
        WHEN REGEXP_MATCHES(LOWER({{ title_col }}), 'isuzu|អ៊ីស៊ូហ្ស៊ុ') THEN 'Isuzu'
        WHEN REGEXP_MATCHES(LOWER({{ title_col }}), 'suzuki|ស៊ុយស៊ូគី') THEN 'Suzuki'
        WHEN REGEXP_MATCHES(LOWER({{ title_col }}), 'subaru') THEN 'Subaru'
        WHEN REGEXP_MATCHES(LOWER({{ title_col }}), 'volkswagen|\bvw\b') THEN 'Volkswagen'
        WHEN REGEXP_MATCHES(LOWER({{ title_col }}), 'chevrolet|\bchevy\b') THEN 'Chevrolet'
        WHEN REGEXP_MATCHES(LOWER({{ title_col }}), '\bjeep\b') THEN 'Jeep'
        WHEN REGEXP_MATCHES(LOWER({{ title_col }}), '\bdodge\b') THEN 'Dodge'
        WHEN REGEXP_MATCHES(LOWER({{ title_col }}), 'cadillac') THEN 'Cadillac'
        WHEN REGEXP_MATCHES(LOWER({{ title_col }}), 'lincoln') THEN 'Lincoln'
        WHEN REGEXP_MATCHES(LOWER({{ title_col }}), '\bgmc\b') THEN 'GMC'
        WHEN REGEXP_MATCHES(LOWER({{ title_col }}), '\baudi\b') THEN 'Audi'
        WHEN REGEXP_MATCHES(LOWER({{ title_col }}), 'porsche') THEN 'Porsche'
        WHEN REGEXP_MATCHES(LOWER({{ title_col }}), 'volvo') THEN 'Volvo'
        WHEN REGEXP_MATCHES(LOWER({{ title_col }}), 'peugeot') THEN 'Peugeot'
        WHEN REGEXP_MATCHES(LOWER({{ title_col }}), '\bbyd\b') THEN 'BYD'
        WHEN REGEXP_MATCHES(LOWER({{ title_col }}), '\bmg\b') THEN 'MG'
        WHEN REGEXP_MATCHES(LOWER({{ title_col }}), 'geely') THEN 'Geely'
        WHEN REGEXP_MATCHES(LOWER({{ title_col }}), 'haval') THEN 'Haval'
        WHEN REGEXP_MATCHES(LOWER({{ title_col }}), '\bgac\b') THEN 'GAC'
        WHEN REGEXP_MATCHES(LOWER({{ title_col }}), 'jetour') THEN 'Jetour'
        WHEN REGEXP_MATCHES(LOWER({{ title_col }}), 'changan') THEN 'Changan'
        WHEN REGEXP_MATCHES(LOWER({{ title_col }}), 'denza') THEN 'Denza'
        WHEN REGEXP_MATCHES(LOWER({{ title_col }}), 'xpeng') THEN 'Xpeng'
        WHEN REGEXP_MATCHES(LOWER({{ title_col }}), '\bnio\b') THEN 'NIO'
        WHEN REGEXP_MATCHES(LOWER({{ title_col }}), 'li auto|li xiang') THEN 'Li Auto'
        WHEN REGEXP_MATCHES(LOWER({{ title_col }}), 'zeekr') THEN 'Zeekr'
        WHEN REGEXP_MATCHES(LOWER({{ title_col }}), 'chery') THEN 'Chery'
        WHEN REGEXP_MATCHES(LOWER({{ title_col }}), 'hongqi') THEN 'Hongqi'
        WHEN REGEXP_MATCHES(LOWER({{ title_col }}), 'tesla') THEN 'Tesla'
        ELSE 'Unknown'
    END
{% endmacro %}


{% macro extract_model_from_raw(raw_model_col, title_col, brand_col) %}
    CASE
        -- ── Toyota Models ────────────────────────────────────────────────────
        WHEN {{ brand_col }} = 'Toyota' THEN
            CASE
                WHEN REGEXP_MATCHES(LOWER({{ title_col }}), '\bprius\b|ព្រូស|ព្រុស') THEN 'Prius'
                WHEN REGEXP_MATCHES(LOWER({{ title_col }}), '\bcamry\b|ខេមរី|ខាមរី') THEN 'Camry'
                WHEN REGEXP_MATCHES(LOWER({{ title_col }}), '\bcorolla\b|កូរ៉ូឡា') THEN 'Corolla'
                WHEN REGEXP_MATCHES(LOWER({{ title_col }}), '\bhighlander\b|ហាយឡែនឌ័រ|ហៃឡែនឌឺ|ហៃឡែន') THEN 'Highlander'
                WHEN REGEXP_MATCHES(LOWER({{ title_col }}), '\brav4\b|រ៉ាវ៤|រ៉ាវ4') THEN 'RAV4'
                WHEN REGEXP_MATCHES(LOWER({{ title_col }}), 'land\s*cruiser\s*prado|prado\b|ប្រាដូ') THEN 'Land Cruiser Prado'
                WHEN REGEXP_MATCHES(LOWER({{ title_col }}), 'land\s*cruiser\b|ឡង់គ្រីស័រ') THEN 'Land Cruiser'
                WHEN REGEXP_MATCHES(LOWER({{ title_col }}), 'hilux\s*revo|revo\b') THEN 'Hilux Revo'
                WHEN REGEXP_MATCHES(LOWER({{ title_col }}), 'hilux\s*vigo|vigo\b') THEN 'Hilux Vigo'
                WHEN REGEXP_MATCHES(LOWER({{ title_col }}), 'hilux\b') THEN 'Hilux'
                WHEN REGEXP_MATCHES(LOWER({{ title_col }}), 'fortuner\b|ហ្វ័រធូណឺ') THEN 'Fortuner'
                WHEN REGEXP_MATCHES(LOWER({{ title_col }}), 'alphard\b|អាល់ហ្វាត') THEN 'Alphard'
                WHEN REGEXP_MATCHES(LOWER({{ title_col }}), 'vellfire\b') THEN 'Vellfire'
                WHEN REGEXP_MATCHES(LOWER({{ title_col }}), '\bvitz\b') THEN 'Vitz'
                WHEN REGEXP_MATCHES(LOWER({{ title_col }}), '\braize\b') THEN 'Raize'
                WHEN REGEXP_MATCHES(LOWER({{ title_col }}), 'yaris\s*cross') THEN 'Yaris Cross'
                WHEN REGEXP_MATCHES(LOWER({{ title_col }}), 'yaris\b') THEN 'Yaris'
                WHEN REGEXP_MATCHES(LOWER({{ title_col }}), 'sienna\b') THEN 'Sienna'
                WHEN REGEXP_MATCHES(LOWER({{ title_col }}), 'tacoma\b') THEN 'Tacoma'
                WHEN REGEXP_MATCHES(LOWER({{ title_col }}), 'tundra\b') THEN 'Tundra'
                WHEN REGEXP_MATCHES(LOWER({{ title_col }}), 'rush\b') THEN 'Rush'
                WHEN REGEXP_MATCHES(LOWER({{ title_col }}), 'avanza\b') THEN 'Avanza'
                WHEN REGEXP_MATCHES(LOWER({{ title_col }}), 'crown\b') THEN 'Crown'
                WHEN REGEXP_MATCHES(LOWER({{ title_col }}), '4runner\b') THEN '4Runner'
                WHEN {{ raw_model_col }} IS NOT NULL AND {{ raw_model_col }} NOT IN ('', 'Unknown', 'None') THEN {{ raw_model_col }}
                ELSE 'Other_Toyota'
            END

        -- ── Lexus Models ─────────────────────────────────────────────────────
        WHEN {{ brand_col }} = 'Lexus' THEN
            CASE
                WHEN REGEXP_MATCHES(LOWER({{ title_col }}), '\brx\s*300\b|rx300') THEN 'RX300'
                WHEN REGEXP_MATCHES(LOWER({{ title_col }}), '\brx\s*330\b|rx330') THEN 'RX330'
                WHEN REGEXP_MATCHES(LOWER({{ title_col }}), '\brx\s*350\b|rx350') THEN 'RX350'
                WHEN REGEXP_MATCHES(LOWER({{ title_col }}), '\brx\s*450h?\b|rx450') THEN 'RX450h'
                WHEN REGEXP_MATCHES(LOWER({{ title_col }}), '\brx\s*200t\b|rx200t') THEN 'RX200t'
                WHEN REGEXP_MATCHES(LOWER({{ title_col }}), '\bnx\s*200t\b|nx200t') THEN 'NX200t'
                WHEN REGEXP_MATCHES(LOWER({{ title_col }}), '\bnx\s*300h?\b|nx300') THEN 'NX300'
                WHEN REGEXP_MATCHES(LOWER({{ title_col }}), '\blx\s*570\b|lx570') THEN 'LX570'
                WHEN REGEXP_MATCHES(LOWER({{ title_col }}), '\blx\s*600\b|lx600') THEN 'LX600'
                WHEN REGEXP_MATCHES(LOWER({{ title_col }}), '\blx\s*470\b|lx470') THEN 'LX470'
                WHEN REGEXP_MATCHES(LOWER({{ title_col }}), '\bgx\s*460\b|gx460') THEN 'GX460'
                WHEN REGEXP_MATCHES(LOWER({{ title_col }}), '\bgx\s*470\b|gx470') THEN 'GX470'
                WHEN REGEXP_MATCHES(LOWER({{ title_col }}), '\bes\s*350\b|es350') THEN 'ES350'
                WHEN REGEXP_MATCHES(LOWER({{ title_col }}), '\bes\s*300h?\b|es300') THEN 'ES300'
                WHEN REGEXP_MATCHES(LOWER({{ title_col }}), '\bct\s*200h?\b|ct200') THEN 'CT200h'
                WHEN REGEXP_MATCHES(LOWER({{ title_col }}), '\bis\s*250\b|is250') THEN 'IS250'
                WHEN REGEXP_MATCHES(LOWER({{ title_col }}), '\bgs\s*300\b|gs300') THEN 'GS300'
                WHEN {{ raw_model_col }} IS NOT NULL AND {{ raw_model_col }} NOT IN ('', 'Unknown', 'None') THEN {{ raw_model_col }}
                ELSE 'Other_Lexus'
            END

        -- ── Ford Models ──────────────────────────────────────────────────────
        WHEN {{ brand_col }} = 'Ford' THEN
            CASE
                WHEN REGEXP_MATCHES(LOWER({{ title_col }}), 'ranger\s*raptor|raptor\b') THEN 'Ranger Raptor'
                WHEN REGEXP_MATCHES(LOWER({{ title_col }}), 'ranger\s*wildtrak|wildtrak\b') THEN 'Ranger Wildtrak'
                WHEN REGEXP_MATCHES(LOWER({{ title_col }}), 'ranger\b') THEN 'Ranger'
                WHEN REGEXP_MATCHES(LOWER({{ title_col }}), 'everest\b|អេវឺរ៉េស') THEN 'Everest'
                WHEN REGEXP_MATCHES(LOWER({{ title_col }}), 'explorer\b') THEN 'Explorer'
                WHEN REGEXP_MATCHES(LOWER({{ title_col }}), 'territory\b') THEN 'Territory'
                WHEN REGEXP_MATCHES(LOWER({{ title_col }}), 'f[- ]?150') THEN 'F-150'
                WHEN REGEXP_MATCHES(LOWER({{ title_col }}), 'mustang\b') THEN 'Mustang'
                WHEN {{ raw_model_col }} IS NOT NULL AND {{ raw_model_col }} NOT IN ('', 'Unknown', 'None') THEN {{ raw_model_col }}
                ELSE 'Other_Ford'
            END

        -- ── Hyundai Models ───────────────────────────────────────────────────
        WHEN {{ brand_col }} = 'Hyundai' THEN
            CASE
                WHEN REGEXP_MATCHES(LOWER({{ title_col }}), 'grand\s*starex|starex\b|ស្តារិច') THEN 'Starex'
                WHEN REGEXP_MATCHES(LOWER({{ title_col }}), 'santa\s*fe\b|សាន់តាផេ') THEN 'Santa Fe'
                WHEN REGEXP_MATCHES(LOWER({{ title_col }}), 'tucson\b|ទុចសិន') THEN 'Tucson'
                WHEN REGEXP_MATCHES(LOWER({{ title_col }}), 'palisade\b') THEN 'Palisade'
                WHEN REGEXP_MATCHES(LOWER({{ title_col }}), 'custin\b') THEN 'Custin'
                WHEN REGEXP_MATCHES(LOWER({{ title_col }}), 'creta\b') THEN 'Creta'
                WHEN REGEXP_MATCHES(LOWER({{ title_col }}), 'elantra\b') THEN 'Elantra'
                WHEN {{ raw_model_col }} IS NOT NULL AND {{ raw_model_col }} NOT IN ('', 'Unknown', 'None') THEN {{ raw_model_col }}
                ELSE 'Other_Hyundai'
            END

        -- ── Kia Models ───────────────────────────────────────────────────────
        WHEN {{ brand_col }} = 'Kia' THEN
            CASE
                WHEN REGEXP_MATCHES(LOWER({{ title_col }}), 'morning\b|ម៉ូណីង') THEN 'Morning'
                WHEN REGEXP_MATCHES(LOWER({{ title_col }}), 'carnival\b|ខានីវ៉ាល់') THEN 'Carnival'
                WHEN REGEXP_MATCHES(LOWER({{ title_col }}), 'sorento\b|សូរិនតូ') THEN 'Sorento'
                WHEN REGEXP_MATCHES(LOWER({{ title_col }}), 'sportage\b') THEN 'Sportage'
                WHEN REGEXP_MATCHES(LOWER({{ title_col }}), 'seltos\b') THEN 'Seltos'
                WHEN REGEXP_MATCHES(LOWER({{ title_col }}), 'sonet\b') THEN 'Sonet'
                WHEN REGEXP_MATCHES(LOWER({{ title_col }}), '\bk5\b') THEN 'K5'
                WHEN {{ raw_model_col }} IS NOT NULL AND {{ raw_model_col }} NOT IN ('', 'Unknown', 'None') THEN {{ raw_model_col }}
                ELSE 'Other_Kia'
            END

        -- ── Land Rover Models ────────────────────────────────────────────────
        WHEN {{ brand_col }} = 'Land Rover' THEN
            CASE
                WHEN REGEXP_MATCHES(LOWER({{ title_col }}), 'vogue\b') THEN 'Range Rover Vogue'
                WHEN REGEXP_MATCHES(LOWER({{ title_col }}), 'sport\b') THEN 'Range Rover Sport'
                WHEN REGEXP_MATCHES(LOWER({{ title_col }}), 'evoque\b') THEN 'Range Rover Evoque'
                WHEN REGEXP_MATCHES(LOWER({{ title_col }}), 'velar\b') THEN 'Range Rover Velar'
                WHEN REGEXP_MATCHES(LOWER({{ title_col }}), 'defender\b') THEN 'Defender'
                WHEN REGEXP_MATCHES(LOWER({{ title_col }}), 'discovery\b') THEN 'Discovery'
                WHEN REGEXP_MATCHES(LOWER({{ title_col }}), 'range\s*rover') THEN 'Range Rover'
                WHEN {{ raw_model_col }} IS NOT NULL AND {{ raw_model_col }} NOT IN ('', 'Unknown', 'None') THEN {{ raw_model_col }}
                ELSE 'Range Rover'
            END

        -- ── BMW Models ───────────────────────────────────────────────────────
        WHEN {{ brand_col }} = 'BMW' THEN
            CASE
                WHEN REGEXP_MATCHES(LOWER({{ title_col }}), '\bx5\b') THEN 'X5'
                WHEN REGEXP_MATCHES(LOWER({{ title_col }}), '\bx6\b') THEN 'X6'
                WHEN REGEXP_MATCHES(LOWER({{ title_col }}), '\bx7\b') THEN 'X7'
                WHEN REGEXP_MATCHES(LOWER({{ title_col }}), '\bx3\b') THEN 'X3'
                WHEN REGEXP_MATCHES(LOWER({{ title_col }}), '3\s*series|320i|328i|330i') THEN '3 Series'
                WHEN REGEXP_MATCHES(LOWER({{ title_col }}), '5\s*series|520i|528i|530i') THEN '5 Series'
                WHEN REGEXP_MATCHES(LOWER({{ title_col }}), '7\s*series|730li|740li') THEN '7 Series'
                WHEN {{ raw_model_col }} IS NOT NULL AND {{ raw_model_col }} NOT IN ('', 'Unknown', 'None') THEN {{ raw_model_col }}
                ELSE 'Other_BMW'
            END

        -- ── Mazda Models ─────────────────────────────────────────────────────
        WHEN {{ brand_col }} = 'Mazda' THEN
            CASE
                WHEN REGEXP_MATCHES(LOWER({{ title_col }}), 'cx[- ]?5') THEN 'CX-5'
                WHEN REGEXP_MATCHES(LOWER({{ title_col }}), 'cx[- ]?9') THEN 'CX-9'
                WHEN REGEXP_MATCHES(LOWER({{ title_col }}), 'cx[- ]?30') THEN 'CX-30'
                WHEN REGEXP_MATCHES(LOWER({{ title_col }}), 'cx[- ]?8') THEN 'CX-8'
                WHEN REGEXP_MATCHES(LOWER({{ title_col }}), 'bt[- ]?50') THEN 'BT-50'
                WHEN REGEXP_MATCHES(LOWER({{ title_col }}), 'mazda\s*3') THEN 'Mazda 3'
                WHEN REGEXP_MATCHES(LOWER({{ title_col }}), 'mazda\s*2') THEN 'Mazda 2'
                WHEN {{ raw_model_col }} IS NOT NULL AND {{ raw_model_col }} NOT IN ('', 'Unknown', 'None') THEN {{ raw_model_col }}
                ELSE 'Other_Mazda'
            END

        -- ── Mitsubishi Models ────────────────────────────────────────────────
        WHEN {{ brand_col }} = 'Mitsubishi' THEN
            CASE
                WHEN REGEXP_MATCHES(LOWER({{ title_col }}), 'pajero\s*sport') THEN 'Pajero Sport'
                WHEN REGEXP_MATCHES(LOWER({{ title_col }}), 'pajero\b') THEN 'Pajero'
                WHEN REGEXP_MATCHES(LOWER({{ title_col }}), 'triton\b') THEN 'Triton'
                WHEN REGEXP_MATCHES(LOWER({{ title_col }}), 'xpander\b') THEN 'Xpander'
                WHEN REGEXP_MATCHES(LOWER({{ title_col }}), 'outlander\b') THEN 'Outlander'
                WHEN {{ raw_model_col }} IS NOT NULL AND {{ raw_model_col }} NOT IN ('', 'Unknown', 'None') THEN {{ raw_model_col }}
                ELSE 'Other_Mitsubishi'
            END

        -- ── AVATR & Chinese EV Models ────────────────────────────────────────
        WHEN {{ brand_col }} = 'AVATR' THEN
            CASE
                WHEN REGEXP_MATCHES(LOWER({{ title_col }}), '12\b') THEN 'AVATR 12'
                WHEN REGEXP_MATCHES(LOWER({{ title_col }}), '11\b') THEN 'AVATR 11'
                ELSE 'AVATR'
            END

        WHEN {{ raw_model_col }} IS NOT NULL AND {{ raw_model_col }} NOT IN ('', 'Unknown', 'None') THEN {{ raw_model_col }}
        ELSE 'Unknown'
    END
{% endmacro %}
