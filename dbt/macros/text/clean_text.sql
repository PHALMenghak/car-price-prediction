-- dbt/macros/text/clean_text.sql
-- Single-pass text sanitization: Whitespace normalization, HTML unescaping, emoji & zero-width space removal.

{% macro clean_text(col) %}
NULLIF(
    TRIM(
        REGEXP_REPLACE(
            REGEXP_REPLACE(
                REGEXP_REPLACE(
                    REGEXP_REPLACE(
                        REPLACE(
                            REPLACE(
                                REPLACE(
                                    REPLACE(
                                        REGEXP_REPLACE(COALESCE(CAST({{ col }} AS VARCHAR), ''), '<[^>]+>', ' ', 'g'),
                                        chr(8203), ''
                                    ),
                                    chr(8205), ''
                                ),
                                chr(65279), ''
                            ),
                            '&amp;', '&'
                        ),
                        '&#39;|&apos;', '''', 'g'
                    ),
                    '&nbsp;|&quot;|&lt;|&gt;', ' ', 'g'
                ),
                '[\x{1F000}-\x{1FAFF}\x{2600}-\x{27BF}\x{2B00}-\x{2BFF}\x{FE00}-\x{FE0F}\x{FFFC}]', ' ', 'g'
            ),
            '\s+', ' ', 'g'
        )
    ),
    ''
)
{% endmacro %}
