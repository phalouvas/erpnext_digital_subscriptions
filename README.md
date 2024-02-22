## Digital Subscriptions

Sell subscriptions for file download

#### License

MIT

#### How to migrate users from Joomla
For subscriptions: https://erpnext.kainotomo.com/api/method/digital_subscriptions.digital_subscriptions.hooks.migrate.create_subscriptions
For users import: 
```
bench data-import --file User_1.csv --doctype User --type Insert --mute-emails
bench data-import --file User_2.csv --doctype User --type Insert --mute-emails
bench data-import --file User_3.csv --doctype User --type Insert --mute-emails
bench data-import --file User_4.csv --doctype User --type Insert --mute-emails
bench data-import --file User_5.csv --doctype User --type Insert --mute-emails
bench data-import --file User_6.csv --doctype User --type Insert --mute-emails
bench data-import --file User_7.csv --doctype User --type Insert --mute-emails
bench data-import --file User_8.csv --doctype User --type Insert --mute-emails
bench data-import --file User_9.csv --doctype User --type Insert --mute-emails
```