-- dbt/macros/parsing/extract_model_from_title.sql
-- High-accuracy canonical vehicle model extractor from listing title text.
-- Resolves high-volume Cambodian market models when raw model specs are missing or marked as 'ផ្សេងៗ' / 'Other'.

{% macro extract_model_from_title(brand_col, title_col) %}
    CASE
        -- Toyota
        WHEN {{ brand_col }} = 'Toyota' AND REGEXP_MATCHES(LOWER({{ title_col }}), '\bprius\b') THEN 'Prius'
        WHEN {{ brand_col }} = 'Toyota' AND REGEXP_MATCHES(LOWER({{ title_col }}), '\bcamry\b') THEN 'Camry'
        WHEN {{ brand_col }} = 'Toyota' AND REGEXP_MATCHES(LOWER({{ title_col }}), '\bcorolla\s*cross\b') THEN 'Corolla Cross'
        WHEN {{ brand_col }} = 'Toyota' AND REGEXP_MATCHES(LOWER({{ title_col }}), '\bcorolla\b') THEN 'Corolla'
        WHEN {{ brand_col }} = 'Toyota' AND REGEXP_MATCHES(LOWER({{ title_col }}), 'land\s*cruiser\s*prado|prado') THEN 'Land Cruiser Prado'
        WHEN {{ brand_col }} = 'Toyota' AND REGEXP_MATCHES(LOWER({{ title_col }}), 'land\s*cruiser|\blc\b|lc200|lc300') THEN 'Land Cruiser'
        WHEN {{ brand_col }} = 'Toyota' AND REGEXP_MATCHES(LOWER({{ title_col }}), 'hilux\s*revo|revo') THEN 'Hilux Revo'
        WHEN {{ brand_col }} = 'Toyota' AND REGEXP_MATCHES(LOWER({{ title_col }}), 'hilux\s*vigo|vigo') THEN 'Hilux Vigo'
        WHEN {{ brand_col }} = 'Toyota' AND REGEXP_MATCHES(LOWER({{ title_col }}), '\bhilux\b') THEN 'Hilux'
        WHEN {{ brand_col }} = 'Toyota' AND REGEXP_MATCHES(LOWER({{ title_col }}), '\braize\b') THEN 'Raize'
        WHEN {{ brand_col }} = 'Toyota' AND REGEXP_MATCHES(LOWER({{ title_col }}), '\bfortuner\b') THEN 'Fortuner'
        WHEN {{ brand_col }} = 'Toyota' AND REGEXP_MATCHES(LOWER({{ title_col }}), '\bhighlander\b') THEN 'Highlander'
        WHEN {{ brand_col }} = 'Toyota' AND REGEXP_MATCHES(LOWER({{ title_col }}), '\brav4\b|rav\s*4') THEN 'RAV4'
        WHEN {{ brand_col }} = 'Toyota' AND REGEXP_MATCHES(LOWER({{ title_col }}), '\bvellfire\b') THEN 'Vellfire'
        WHEN {{ brand_col }} = 'Toyota' AND REGEXP_MATCHES(LOWER({{ title_col }}), '\balphard\b') THEN 'Alphard'
        WHEN {{ brand_col }} = 'Toyota' AND REGEXP_MATCHES(LOWER({{ title_col }}), '\btacoma\b') THEN 'Tacoma'
        WHEN {{ brand_col }} = 'Toyota' AND REGEXP_MATCHES(LOWER({{ title_col }}), '\btundra\b') THEN 'Tundra'
        WHEN {{ brand_col }} = 'Toyota' AND REGEXP_MATCHES(LOWER({{ title_col }}), '\bsequoia\b') THEN 'Sequoia'
        WHEN {{ brand_col }} = 'Toyota' AND REGEXP_MATCHES(LOWER({{ title_col }}), '\bhiace\b') THEN 'Hiace'
        WHEN {{ brand_col }} = 'Toyota' AND REGEXP_MATCHES(LOWER({{ title_col }}), '\bcrown\b') THEN 'Crown'
        WHEN {{ brand_col }} = 'Toyota' AND REGEXP_MATCHES(LOWER({{ title_col }}), '\bgranvia\b') THEN 'Granvia'
        WHEN {{ brand_col }} = 'Toyota' AND REGEXP_MATCHES(LOWER({{ title_col }}), '\byaris\b') THEN 'Yaris'
        WHEN {{ brand_col }} = 'Toyota' AND REGEXP_MATCHES(LOWER({{ title_col }}), '\bvitz\b') THEN 'Vitz'
        WHEN {{ brand_col }} = 'Toyota' AND REGEXP_MATCHES(LOWER({{ title_col }}), '\bavanza\b') THEN 'Avanza'
        WHEN {{ brand_col }} = 'Toyota' AND REGEXP_MATCHES(LOWER({{ title_col }}), '\brush\b') THEN 'Rush'

        -- Lexus
        WHEN {{ brand_col }} = 'Lexus' AND REGEXP_MATCHES(LOWER({{ title_col }}), '\brx300\b') THEN 'RX300'
        WHEN {{ brand_col }} = 'Lexus' AND REGEXP_MATCHES(LOWER({{ title_col }}), '\brx330\b') THEN 'RX330'
        WHEN {{ brand_col }} = 'Lexus' AND REGEXP_MATCHES(LOWER({{ title_col }}), '\brx350\b') THEN 'RX350'
        WHEN {{ brand_col }} = 'Lexus' AND REGEXP_MATCHES(LOWER({{ title_col }}), '\brx400h\b') THEN 'RX400h'
        WHEN {{ brand_col }} = 'Lexus' AND REGEXP_MATCHES(LOWER({{ title_col }}), '\brx450h\b') THEN 'RX450h'
        WHEN {{ brand_col }} = 'Lexus' AND REGEXP_MATCHES(LOWER({{ title_col }}), '\blx470\b') THEN 'LX470'
        WHEN {{ brand_col }} = 'Lexus' AND REGEXP_MATCHES(LOWER({{ title_col }}), '\blx570\b') THEN 'LX570'
        WHEN {{ brand_col }} = 'Lexus' AND REGEXP_MATCHES(LOWER({{ title_col }}), '\blx600\b') THEN 'LX600'
        WHEN {{ brand_col }} = 'Lexus' AND REGEXP_MATCHES(LOWER({{ title_col }}), '\bgx460\b') THEN 'GX460'
        WHEN {{ brand_col }} = 'Lexus' AND REGEXP_MATCHES(LOWER({{ title_col }}), '\bgx470\b') THEN 'GX470'
        WHEN {{ brand_col }} = 'Lexus' AND REGEXP_MATCHES(LOWER({{ title_col }}), '\bgx550\b') THEN 'GX550'
        WHEN {{ brand_col }} = 'Lexus' AND REGEXP_MATCHES(LOWER({{ title_col }}), '\bnx200t\b') THEN 'NX200t'
        WHEN {{ brand_col }} = 'Lexus' AND REGEXP_MATCHES(LOWER({{ title_col }}), '\bnx300\b') THEN 'NX300'
        WHEN {{ brand_col }} = 'Lexus' AND REGEXP_MATCHES(LOWER({{ title_col }}), '\bnx350\b') THEN 'NX350'
        WHEN {{ brand_col }} = 'Lexus' AND REGEXP_MATCHES(LOWER({{ title_col }}), '\bes300\b') THEN 'ES300'
        WHEN {{ brand_col }} = 'Lexus' AND REGEXP_MATCHES(LOWER({{ title_col }}), '\bes330\b') THEN 'ES330'
        WHEN {{ brand_col }} = 'Lexus' AND REGEXP_MATCHES(LOWER({{ title_col }}), '\bes350\b') THEN 'ES350'
        WHEN {{ brand_col }} = 'Lexus' AND REGEXP_MATCHES(LOWER({{ title_col }}), '\bes300h\b') THEN 'ES300h'

        -- Ford
        WHEN {{ brand_col }} = 'Ford' AND REGEXP_MATCHES(LOWER({{ title_col }}), 'ranger\s*raptor|raptor') THEN 'Ranger Raptor'
        WHEN {{ brand_col }} = 'Ford' AND REGEXP_MATCHES(LOWER({{ title_col }}), 'ranger\s*wildtrak|wildtrak') THEN 'Ranger Wildtrak'
        WHEN {{ brand_col }} = 'Ford' AND REGEXP_MATCHES(LOWER({{ title_col }}), '\branger\b') THEN 'Ranger'
        WHEN {{ brand_col }} = 'Ford' AND REGEXP_MATCHES(LOWER({{ title_col }}), '\beverest\b') THEN 'Everest'
        WHEN {{ brand_col }} = 'Ford' AND REGEXP_MATCHES(LOWER({{ title_col }}), '\bterritory\b') THEN 'Territory'
        WHEN {{ brand_col }} = 'Ford' AND REGEXP_MATCHES(LOWER({{ title_col }}), 'f-?150') THEN 'F-150'
        WHEN {{ brand_col }} = 'Ford' AND REGEXP_MATCHES(LOWER({{ title_col }}), '\bexplorer\b') THEN 'Explorer'
        WHEN {{ brand_col }} = 'Ford' AND REGEXP_MATCHES(LOWER({{ title_col }}), '\becosport\b') THEN 'EcoSport'

        -- Mercedes-Benz
        WHEN {{ brand_col }} = 'Mercedes-Benz' AND REGEXP_MATCHES(LOWER({{ title_col }}), '\bg-?class\b|\bg63\b|\bg500\b|\bg55\b') THEN 'G-Class'
        WHEN {{ brand_col }} = 'Mercedes-Benz' AND REGEXP_MATCHES(LOWER({{ title_col }}), '\bc-?class\b|\bc200\b|\bc300\b|\bc250\b|\bc180\b') THEN 'C-Class'
        WHEN {{ brand_col }} = 'Mercedes-Benz' AND REGEXP_MATCHES(LOWER({{ title_col }}), '\be-?class\b|\be200\b|\be300\b|\be250\b|\be350\b') THEN 'E-Class'
        WHEN {{ brand_col }} = 'Mercedes-Benz' AND REGEXP_MATCHES(LOWER({{ title_col }}), '\bs-?class\b|\bs400\b|\bs500\b|\bs450\b|\bs550\b|\bs580\b') THEN 'S-Class'
        WHEN {{ brand_col }} = 'Mercedes-Benz' AND REGEXP_MATCHES(LOWER({{ title_col }}), '\bglc\b|\bglc200\b|\bglc300\b') THEN 'GLC'
        WHEN {{ brand_col }} = 'Mercedes-Benz' AND REGEXP_MATCHES(LOWER({{ title_col }}), '\bgle\b|\bgle450\b|\bgle400\b|\bgle53\b') THEN 'GLE'
        WHEN {{ brand_col }} = 'Mercedes-Benz' AND REGEXP_MATCHES(LOWER({{ title_col }}), '\bgls\b|\bgls450\b|\bgls500\b|\bgls600\b') THEN 'GLS'
        WHEN {{ brand_col }} = 'Mercedes-Benz' AND REGEXP_MATCHES(LOWER({{ title_col }}), '\bcla\b|\bcla200\b|\bcla250\b') THEN 'CLA'

        -- BMW
        WHEN {{ brand_col }} = 'BMW' AND REGEXP_MATCHES(LOWER({{ title_col }}), '\bx5\b') THEN 'X5'
        WHEN {{ brand_col }} = 'BMW' AND REGEXP_MATCHES(LOWER({{ title_col }}), '\bx6\b') THEN 'X6'
        WHEN {{ brand_col }} = 'BMW' AND REGEXP_MATCHES(LOWER({{ title_col }}), '\bx7\b') THEN 'X7'
        WHEN {{ brand_col }} = 'BMW' AND REGEXP_MATCHES(LOWER({{ title_col }}), '\bx3\b') THEN 'X3'
        WHEN {{ brand_col }} = 'BMW' AND REGEXP_MATCHES(LOWER({{ title_col }}), '\bx4\b') THEN 'X4'
        WHEN {{ brand_col }} = 'BMW' AND REGEXP_MATCHES(LOWER({{ title_col }}), '\bx1\b') THEN 'X1'
        WHEN {{ brand_col }} = 'BMW' AND REGEXP_MATCHES(LOWER({{ title_col }}), '\b3\s*series\b|\b320i\b|\b328i\b|\b330i\b') THEN '3 Series'
        WHEN {{ brand_col }} = 'BMW' AND REGEXP_MATCHES(LOWER({{ title_col }}), '\b5\s*series\b|\b520i\b|\b528i\b|\b530i\b') THEN '5 Series'
        WHEN {{ brand_col }} = 'BMW' AND REGEXP_MATCHES(LOWER({{ title_col }}), '\b7\s*series\b|\b730li\b|\b740li\b|\b750li\b') THEN '7 Series'

        -- Hyundai
        WHEN {{ brand_col }} = 'Hyundai' AND REGEXP_MATCHES(LOWER({{ title_col }}), '\bpalisade\b') THEN 'Palisade'
        WHEN {{ brand_col }} = 'Hyundai' AND REGEXP_MATCHES(LOWER({{ title_col }}), '\bsanta\s*fe\b') THEN 'Santa Fe'
        WHEN {{ brand_col }} = 'Hyundai' AND REGEXP_MATCHES(LOWER({{ title_col }}), '\btucson\b') THEN 'Tucson'
        WHEN {{ brand_col }} = 'Hyundai' AND REGEXP_MATCHES(LOWER({{ title_col }}), '\bh-?1\b|\bstarex\b') THEN 'Starex'
        WHEN {{ brand_col }} = 'Hyundai' AND REGEXP_MATCHES(LOWER({{ title_col }}), '\bstaria\b') THEN 'Staria'
        WHEN {{ brand_col }} = 'Hyundai' AND REGEXP_MATCHES(LOWER({{ title_col }}), '\bcreta\b') THEN 'Creta'
        WHEN {{ brand_col }} = 'Hyundai' AND REGEXP_MATCHES(LOWER({{ title_col }}), '\bcustin\b') THEN 'Custin'

        -- Kia
        WHEN {{ brand_col }} = 'Kia' AND REGEXP_MATCHES(LOWER({{ title_col }}), '\bcarnival\b|\bsedona\b') THEN 'Carnival'
        WHEN {{ brand_col }} = 'Kia' AND REGEXP_MATCHES(LOWER({{ title_col }}), '\bsorento\b') THEN 'Sorento'
        WHEN {{ brand_col }} = 'Kia' AND REGEXP_MATCHES(LOWER({{ title_col }}), '\bsportage\b') THEN 'Sportage'
        WHEN {{ brand_col }} = 'Kia' AND REGEXP_MATCHES(LOWER({{ title_col }}), '\bmorning\b|\bpicanto\b') THEN 'Morning'
        WHEN {{ brand_col }} = 'Kia' AND REGEXP_MATCHES(LOWER({{ title_col }}), '\bray\b') THEN 'Ray'
        WHEN {{ brand_col }} = 'Kia' AND REGEXP_MATCHES(LOWER({{ title_col }}), '\bsonet\b') THEN 'Sonet'
        WHEN {{ brand_col }} = 'Kia' AND REGEXP_MATCHES(LOWER({{ title_col }}), '\bseltos\b') THEN 'Seltos'

        -- Mazda
        WHEN {{ brand_col }} = 'Mazda' AND REGEXP_MATCHES(LOWER({{ title_col }}), '\bcx-?5\b') THEN 'CX-5'
        WHEN {{ brand_col }} = 'Mazda' AND REGEXP_MATCHES(LOWER({{ title_col }}), '\bcx-?9\b') THEN 'CX-9'
        WHEN {{ brand_col }} = 'Mazda' AND REGEXP_MATCHES(LOWER({{ title_col }}), '\bcx-?3\b') THEN 'CX-3'
        WHEN {{ brand_col }} = 'Mazda' AND REGEXP_MATCHES(LOWER({{ title_col }}), '\bcx-?30\b') THEN 'CX-30'
        WHEN {{ brand_col }} = 'Mazda' AND REGEXP_MATCHES(LOWER({{ title_col }}), '\bmazda\s*2\b') THEN 'Mazda 2'
        WHEN {{ brand_col }} = 'Mazda' AND REGEXP_MATCHES(LOWER({{ title_col }}), '\bmazda\s*3\b') THEN 'Mazda 3'
        WHEN {{ brand_col }} = 'Mazda' AND REGEXP_MATCHES(LOWER({{ title_col }}), '\bbt-?50\b') THEN 'BT-50'

        -- Mitsubishi
        WHEN {{ brand_col }} = 'Mitsubishi' AND REGEXP_MATCHES(LOWER({{ title_col }}), '\bpajero\s*sport\b') THEN 'Pajero Sport'
        WHEN {{ brand_col }} = 'Mitsubishi' AND REGEXP_MATCHES(LOWER({{ title_col }}), '\bpajero\b') THEN 'Pajero'
        WHEN {{ brand_col }} = 'Mitsubishi' AND REGEXP_MATCHES(LOWER({{ title_col }}), '\bxpander\b') THEN 'Xpander'
        WHEN {{ brand_col }} = 'Mitsubishi' AND REGEXP_MATCHES(LOWER({{ title_col }}), '\btriton\b') THEN 'Triton'
        WHEN {{ brand_col }} = 'Mitsubishi' AND REGEXP_MATCHES(LOWER({{ title_col }}), '\boutlander\b') THEN 'Outlander'
        WHEN {{ brand_col }} = 'Mitsubishi' AND REGEXP_MATCHES(LOWER({{ title_col }}), '\bxforce\b') THEN 'Xforce'

        -- Nissan
        WHEN {{ brand_col }} = 'Nissan' AND REGEXP_MATCHES(LOWER({{ title_col }}), '\bnavara\b') THEN 'Navara'
        WHEN {{ brand_col }} = 'Nissan' AND REGEXP_MATCHES(LOWER({{ title_col }}), '\bx-?trail\b') THEN 'X-Trail'
        WHEN {{ brand_col }} = 'Nissan' AND REGEXP_MATCHES(LOWER({{ title_col }}), '\bmarch\b') THEN 'March'
        WHEN {{ brand_col }} = 'Nissan' AND REGEXP_MATCHES(LOWER({{ title_col }}), '\bpatrol\b') THEN 'Patrol'
        WHEN {{ brand_col }} = 'Nissan' AND REGEXP_MATCHES(LOWER({{ title_col }}), '\bkicks\b') THEN 'Kicks'
        WHEN {{ brand_col }} = 'Nissan' AND REGEXP_MATCHES(LOWER({{ title_col }}), '\bterra\b') THEN 'Terra'

        -- Honda
        WHEN {{ brand_col }} = 'Honda' AND REGEXP_MATCHES(LOWER({{ title_col }}), '\bcr-?v\b') THEN 'CR-V'
        WHEN {{ brand_col }} = 'Honda' AND REGEXP_MATCHES(LOWER({{ title_col }}), '\bcivic\b') THEN 'Civic'
        WHEN {{ brand_col }} = 'Honda' AND REGEXP_MATCHES(LOWER({{ title_col }}), '\bcity\b') THEN 'City'
        WHEN {{ brand_col }} = 'Honda' AND REGEXP_MATCHES(LOWER({{ title_col }}), '\bhr-?v\b') THEN 'HR-V'
        WHEN {{ brand_col }} = 'Honda' AND REGEXP_MATCHES(LOWER({{ title_col }}), '\baccord\b') THEN 'Accord'
        WHEN {{ brand_col }} = 'Honda' AND REGEXP_MATCHES(LOWER({{ title_col }}), '\bfit\b|\bjazz\b') THEN 'Fit'

        -- BYD
        WHEN {{ brand_col }} = 'BYD' AND REGEXP_MATCHES(LOWER({{ title_col }}), '\batto\s*3\b') THEN 'Atto 3'
        WHEN {{ brand_col }} = 'BYD' AND REGEXP_MATCHES(LOWER({{ title_col }}), '\bseal\b') THEN 'Seal'
        WHEN {{ brand_col }} = 'BYD' AND REGEXP_MATCHES(LOWER({{ title_col }}), '\bdolphin\b') THEN 'Dolphin'
        WHEN {{ brand_col }} = 'BYD' AND REGEXP_MATCHES(LOWER({{ title_col }}), '\bhan\b') THEN 'Han'
        WHEN {{ brand_col }} = 'BYD' AND REGEXP_MATCHES(LOWER({{ title_col }}), '\btang\b') THEN 'Tang'
        WHEN {{ brand_col }} = 'BYD' AND REGEXP_MATCHES(LOWER({{ title_col }}), '\bsong\b') THEN 'Song'
        WHEN {{ brand_col }} = 'BYD' AND REGEXP_MATCHES(LOWER({{ title_col }}), '\bseagull\b') THEN 'Seagull'

        -- Tesla
        WHEN {{ brand_col }} = 'Tesla' AND REGEXP_MATCHES(LOWER({{ title_col }}), 'model\s*3') THEN 'Model 3'
        WHEN {{ brand_col }} = 'Tesla' AND REGEXP_MATCHES(LOWER({{ title_col }}), 'model\s*y') THEN 'Model Y'
        WHEN {{ brand_col }} = 'Tesla' AND REGEXP_MATCHES(LOWER({{ title_col }}), 'model\s*x') THEN 'Model X'
        WHEN {{ brand_col }} = 'Tesla' AND REGEXP_MATCHES(LOWER({{ title_col }}), 'model\s*s') THEN 'Model S'
        WHEN {{ brand_col }} = 'Tesla' AND REGEXP_MATCHES(LOWER({{ title_col }}), 'cybertruck') THEN 'Cybertruck'

        -- High-Volume Modern EV & Crossover Models (Khmer24 'ផ្សេងៗ' Title Fallbacks)
        WHEN ({{ brand_col }} IN ('iCar', 'Chery') OR {{ title_col }} ILIKE '%icar%') AND REGEXP_MATCHES(LOWER({{ title_col }}), '\b(v23|v23s)\b') THEN 'V23'
        WHEN {{ brand_col }} = 'iCar' AND REGEXP_MATCHES(LOWER({{ title_col }}), '\b03\b') THEN '03'
        WHEN ({{ brand_col }} = 'Xiaomi' OR {{ title_col }} ILIKE '%xiaomi%') AND REGEXP_MATCHES(LOWER({{ title_col }}), '\b(su7|yu7)\b') THEN 'SU7'
        WHEN ({{ brand_col }} IN ('Deepal', 'Changan') OR {{ title_col }} ILIKE '%deepal%') AND REGEXP_MATCHES(LOWER({{ title_col }}), '\bs05\b') THEN 'S05'
        WHEN ({{ brand_col }} IN ('Deepal', 'Changan') OR {{ title_col }} ILIKE '%deepal%') AND REGEXP_MATCHES(LOWER({{ title_col }}), '\bs07\b') THEN 'S07'
        WHEN ({{ brand_col }} = 'Changan' OR {{ title_col }} ILIKE '%changan%') AND REGEXP_MATCHES(LOWER({{ title_col }}), '\b(uni-z|uniz)\b') THEN 'UNI-Z'
        WHEN ({{ brand_col }} = 'Changan' OR {{ title_col }} ILIKE '%changan%') AND REGEXP_MATCHES(LOWER({{ title_col }}), '\bq05\b') THEN 'Q05'
        WHEN {{ brand_col }} = 'Nissan' AND REGEXP_MATCHES(LOWER({{ title_col }}), '\bnx8\b') THEN 'NX8'
        WHEN {{ brand_col }} = 'Geely' AND REGEXP_MATCHES(LOWER({{ title_col }}), 'starship\s*7') THEN 'Galaxy Starship 7'
        WHEN {{ brand_col }} = 'Geely' AND REGEXP_MATCHES(LOWER({{ title_col }}), '\bm9\b') THEN 'Galaxy M9'
        WHEN {{ brand_col }} = 'Bestune' AND REGEXP_MATCHES(LOWER({{ title_col }}), 'joyee\s*07') THEN 'Joyee 07'

        ELSE NULL
    END
{% endmacro %}
