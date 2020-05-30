from classes import Team
import utils
import glicko

def processYear(year, all_teams):
    matches = utils.loadMatches(year)
    teams = {}

    try: teams_1yr = utils.loadTeams(year-1)
    except Exception as e: teams_1yr = None

    try: teams_2yr = utils.loadTeams(year-2)
    except Exception as e: teams_2yr = None

    for match in matches:
        for alliance in [match.red, match.blue]:
            for team in alliance:
                if team not in teams:
                    if year==2002: teams[team] = Team(team, [1500, 350])
                    else:
                        if teams_1yr!=None and team in teams_1yr: team_1yr = teams_1yr[team].get_rating_max()
                        else: team_1yr = glicko.new_rating()

                        if teams_2yr!=None and team in teams_2yr: team_2yr = teams_2yr[team].get_rating_max()
                        else: team_2yr = glicko.new_rating()

                        teams[team] = Team(team, glicko.existing_rating(team_1yr, team_2yr))

    for match in matches: glicko.update_rating(year, teams, match)
    utils.saveProcessedMatches(year, matches)
    utils.saveTeams(year, teams)

    for team in teams:
        all_teams.add(team)

def processYears(startYear, endYear):
    all_teams = set()
    for year in range(startYear, endYear+1):
        print(year)
        processYear(year, all_teams)
    utils.saveAllTeams(all_teams)

if __name__ == "__main__":
    processYears(2002, 2020)
