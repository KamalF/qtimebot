import logging
import re
import datetime
import holidays
from redminelib import Redmine

REDMINE = Redmine('https://support.intersec.com', key=REDMINE_KEY)

logging.basicConfig(level=logging.DEBUG)

from slack_bolt import App

app = App()

view_state = {}

@app.middleware  # or app.use(log_request)
def log_request(logger, body, next):
    #logger.debug(body)
    return next()

@app.event("app_home_opened")
def update_home_tab(client, event, logger):
  try:
    client.views_publish(
      # the user that opened your app's app home
      user_id=event["user"],
      # the view object that appears in the app home
      view={
        "type": "home",
        "callback_id": "home_view",

        # body of the view
        "blocks": [
          {
            "type": "section",
            "text": {
              "type": "mrkdwn",
              "text": "*Welcome to Timebot's homepage*"
            }
          },
          {
            "type": "divider"
          },
          {
            "type": "section",
            "text": {
              "type": "mrkdwn",
              "text": "Use the button below to send your weekly activity"
            }
          },
          {
            "type": "actions",
            "elements": [
              {
                "type": "button",
                "action_id": "report_button",
                "text": {
                  "type": "plain_text",
                  "text": "Report"
                }
              }
            ]
          }
        ]
      }
    )

  except Exception as e:
    logger.error(f"Error publishing home tab: {e}")

def retrieve_tickets(context, body, logger):
    tickets = []
    if context["edit-mode"]:
        values=body["view"]["state"]["values"]
        for value in values:
            tickets.append(value)
        logger.debug(tickets[:-2])
        context["tickets-list"] = []
        for ticket in tickets[:-2]:
            issue = REDMINE.issue.get(ticket)
            title = '#' + ticket + ' ' + issue.subject[0:50]

            context["tickets-list"].append(
                {
                    "text": {
                        "type": "plain_text",
                        "text": f"{title}",
                        "emoji": True,
                    },
                    "value": f"{ticket}"
                }
            )
    else:
        options=body["view"]["state"]["values"]["tickets"]["select_ticket"]["selected_options"]
        for option in options:
            tickets.append(option["value"])
        logger.debug(tickets)
        context["tickets-block"] = []
        for ticket in tickets:
            issue = REDMINE.issue.get(ticket)
            title = '#' + ticket + ' ' + issue.subject[0:50]

            context["tickets-block"].append(
                {
                    "type": "input",
                    "block_id": f"{ticket}",
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "res_input",
                        "placeholder": {
                            "type": "plain_text",
                            "text": "Nb of days (e.g. 1.5)"
                        },
                    },
                    "label": {
                        "type": "plain_text",
                        "text": f"{title}",
                        "emoji": True
                    }
                }
            )
        context["tickets-block"].append(
            {
                "type": "input",
                "block_id": "other",
                "element": {
                    "type": "plain_text_input",
                    "action_id": "res_input",
                    "initial_value": "0",
                },
                "label": {
                    "type": "plain_text",
                    "text": "Other",
                    "emoji": True
                }
            }
        )
        context["tickets-block"].append(
            {
                "type": "input",
                "block_id": "days_off",
                "element": {
                    "type": "plain_text_input",
                    "action_id": "res_input",
                    "initial_value": "0",
                },
                "label": {
                    "type": "plain_text",
                    "text": "Days off",
                    "emoji": True
                }
            }
        )


def get_week_info(day):
    week_nb = day.isocalendar()[1]
    monday = day + datetime.timedelta(days=-day.weekday())
    friday = monday + datetime.timedelta(days=5)
    week_str = str(week_nb) + ' (' + monday.strftime("%d/%m") + '-' \
                                  + friday.strftime("%d/%m") + ')'
    nb_days_worked = 5 - len(holidays.France()[monday:friday])

    #Lundi de Pentecôte is worked
    pentecote = holidays.France().get_named('Pentecôte')
    if pentecote and pentecote[0] in holidays.France()[monday:friday]:
        nb_days_worked += 1

    return week_str, nb_days_worked

def get_view(context):
    day = context["day"]
    week_str, nb_days_worked = get_week_info(day)
    tickets_options = []
    if "tickets-list" in context:
        tickets_options = context["tickets-list"]

    if context["edit-mode"]:
        blocks = [
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "plain_text",
                            "text": "You can change the week of the report below",
                            "emoji": True
                            }
                        ]
                    },
                {
                    "type": "actions",
                    "block_id": "date",
                    "elements": [
                        {
                            "type": "datepicker",
                            "initial_date": f"{day}",
                            "placeholder": {
                                "type": "plain_text",
                                "text": "Any date from the week to fill",
                                "emoji": True
                                },
                            "action_id": "datepicker-action"
                            }
                        ]
                },
                {
                    "type": "input",
                    "block_id": "tickets",
                    "element": {
                        "type": "multi_external_select",
                        "action_id": "select_ticket",
                        "placeholder": {
                            "type": "plain_text",
                            "text": "Choose tickets"
                        },
                        "initial_options": tickets_options,
                        "min_query_length": 4
                    },
                    "label": {"type": "plain_text", "text": "Ticket(s) I worked on this week"},
                },
                {
                    "type": "actions",
                    "block_id": "done",
                    "elements": [
                        {
                            "type": "button",
                            "text": {
                                "type": "plain_text",
                                "text": "Done",
                                "emoji": True
                                },
                            "action_id": "on-done",
                            "value": "done",
                            "style": "primary"
                            }
                        ]
                    }
            ]
    else:
        blocks = context["tickets-block"]
        blocks.append(
                {
                    "type": "actions",
                    "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "Back to selection",
                            "emoji": True
                            },
                        "action_id": "edit-mode",
                        "value": "back",
                        "style": "danger"
                        }
                    ]
                }
        )
        blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*{nb_days_worked}* days ON to fill"
                        }
                    }
        )

    return {
            "type": "modal",
            "callback_id": "view-id",
            "private_metadata": f"{day}",
            "title": {
                "type": "plain_text",
                "text": f"Week {week_str}",
                },
            "submit": {
                "type": "plain_text",
                "text": "Submit",
                },
            "close": {
                "type": "plain_text",
                "text": "Cancel",
                },
            "blocks": blocks
        }

@app.action("report_button")
@app.command("/timebot")
def timebot(body, ack, respond, client, logger, context):
    ack()
    #logger.info(body)
    context["day"] = datetime.date.today()
    context["edit-mode"] = True
    res = client.views_open(
        trigger_id=body["trigger_id"],
        view=get_view(context)
    )
    #logger.info(res)

@app.action("datepicker-action")
def time_update(ack, body, response, client, logger, context):
    ack()
    #logger.debug(body)
    date_str = body["view"]["state"]["values"]["date"]["datepicker-action"]["selected_date"]
    context["day"] = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
    context["edit-mode"] = True
    retrieve_tickets(context, body, logger)
    res = client.views_update(
        trigger_id=body["trigger_id"],
        view_id=body["container"]["view_id"],
        view=get_view(context)
    )
    #logger.info(res)

@app.options("select_ticket")
def show_ticket(ack, body, logger):
    ticket_nb = body["value"]
    try:
        issue = REDMINE.issue.get(ticket_nb)
        title = '#' + ticket_nb + ' ' + issue.subject[0:50]
        ack(
                {
                    "options": [
                        {
                            "text": {"type": "plain_text", "text": f"{title}"},
                            "value": f"{ticket_nb}",
                            },
                        ],
                    }
                )
    except:
        ack(
                {
                    "options": []
                    }
                )

@app.action("on-done")
def click_done(ack, body, client, logger, context):
    ack()
    logger.debug(body["view"]["state"]["values"])
    context["edit-mode"] = False
    date_str = body["view"]["state"]["values"]["date"]["datepicker-action"]["selected_date"]
    context["day"] = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
    retrieve_tickets(context, body, logger)
    res = client.views_update(
        trigger_id=body["trigger_id"],
        view_id=body["container"]["view_id"],
        view=get_view(context)
    )

@app.action("edit-mode")
def click_back(ack, body, client, logger, context):
    ack()
    context["edit-mode"] = True
    date_str = body["view"]["private_metadata"]
    context["day"] = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
    retrieve_tickets(context, body, logger)
    res = client.views_update(
        trigger_id=body["trigger_id"],
        view_id=body["container"]["view_id"],
        view=get_view(context)
    )

@app.view("view-id")
def view_submission(ack, body, logger):
    logger.info(body["view"])
    if "date" in body["view"]["state"]["values"]:
        ack(
            {
                "response_action": "errors",
                "errors": {
                    "tickets": "Please press the Done button below"
                }
            }
        )
    else:
        date_str = body["view"]["private_metadata"]
        day = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
        week_str, nb_days_worked = get_week_info(day)
        sum=0
        for res in body["view"]["state"]["values"]:
            sum += float(body["view"]["state"]["values"][res]["res_input"]["value"])

        if sum != nb_days_worked:
            ack(
                {
                    "response_action": "errors",
                    "errors": {
                        "days_off": f"Total sum should be {nb_days_worked}"
                    }
                }
            )
        else:
            ack()
            infos = ''
            for res in body["view"]["state"]["values"]:
                infos += res + ' ' + body["view"]["state"]["values"][res]["res_input"]["value"] + ', '

            logger.info(infos[:-2])

if __name__ == "__main__":
    app.start(3000)
