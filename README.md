# OMNIS Library Integration for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![GitHub Release](https://img.shields.io/github/release/TheUndefined/omnis-ha.svg)](https://github.com/TheUndefined/omnis-ha/releases)

Integration for library accounts using the OMNIS system (Ex Libris Primo). Currently optimized for **Biblioteka Raczyńskich** (Poznań), but configurable for other institutions.

Integracja kont bibliotecznych systemu OMNIS (Ex Libris Primo). Obecnie zoptymalizowana dla **Biblioteki Raczyńskich** w Poznaniu, ale konfigurowalna dla innych instytucji.

## Features / Funkcjonalności

*   📚 **Loans monitoring / Monitorowanie wypożyczeń**:
    *   Total loans count / Całkowita liczba wypożyczonych książek.
    *   Loans per library branch / Wypożyczenia z podziałem na filie.
*   📅 **Due Dates / Terminy zwrotów**:
    *   "Next Due" sensor showing the nearest return date / Sensor "Najbliższy zwrot" pokazujący datę najbliższego zwrotu.
    *   Calendar entity with all due dates / Kalendarz z terminami zwrotów wszystkich książek.
    *   Attributes include days remaining, book title, and location / Atrybuty zawierają liczbę pozostałych dni, tytuł książki i filię.
*   💰 **Fines / Kary**:
    *   Monitoring of account balance and fines / Monitorowanie salda kar na koncie.
*   🔄 **Renewals / Prolongaty**:
    *   Service `omnis.renew_loan` to renew books directly from HA / Usługa do prolongowania książek bezpośrednio z HA.

## Installation / Instalacja

### HACS (Recommended)

1.  Open HACS > Integrations > 3 dots (top right) > Custom repositories.
2.  Add `https://github.com/TheUndefined/omnis-ha` as an Integration.
3.  Click "Download".
4.  Restart Home Assistant.

### Manual

1.  Copy the `custom_components/omnis` folder to your HA `config/custom_components/` directory.
2.  Restart Home Assistant.

## Configuration / Konfiguracja

1.  Go to Settings > Devices & Services.
2.  Click "+ Add Integration".
3.  Search for **OMNIS Library**.
4.  Enter your library credentials (username and password).
5.  Select your library (e.g., "Biblioteka Raczyńskich") or choose "Custom" to enter API details manually.

## Dashboard Card Example / Przykładowa karta

You can use the Markdown card to display a nice table of loans:
Możesz użyć karty Markdown, aby wyświetlić ładną tabelę wypożyczeń:

```yaml
type: markdown
content: >
  {% set all_loans = namespace(list=[]) %}
  {% set today = now().date() %}
  
  {% for state in states.sensor %}
    {% if state.attributes.loans is defined and state.attributes.loans is iterable %}
      {% set user = state.attributes.display_name | default('Unknown') %}
      {% for loan in state.attributes.loans %}
        {% set due = strptime(loan.due_date, '%Y-%m-%d').date() %}
        {% set delta = (due - today).days %}
        {% set loan_data = dict(loan, user=user, delta=delta, due_obj=due) %}
        {% set all_loans.list = all_loans.list + [loan_data] %}
      {% endfor %}
    {% endif %}
  {% endfor %}

  {% if all_loans.list | length == 0 %}
  No active loans.
  {% else %}
  
  {% set grouped = all_loans.list | sort(attribute='location') | groupby('location') %}

  {% for location, loans in grouped %}
  ## 🏛️ {{ location }}
  
  | Due Date | Days | Book | User |
  | :--- | :---: | :--- | :--- |
  {% for loan in loans | sort(attribute='due_obj') %}
  {%- if loan.delta < 0 -%}
  | 🔴 **{{ loan.due_date }}** | **{{ loan.delta }}** | {{ loan.title }} | {{ loan.user }} |
  {%- elif loan.delta <= 3 -%}
  | 🟠 {{ loan.due_date }} | {{ loan.delta }} | {{ loan.title }} | {{ loan.user }} |
  {%- else -%}
  | 🟢 {{ loan.due_date }} | {{ loan.delta }} | {{ loan.title }} | {{ loan.user }} |
  {%- endif -%}
  {% endfor %}
  
  ---
  {% endfor %}
  {% endif %}
title: Loans Overview
```
