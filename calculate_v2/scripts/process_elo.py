import statistics

from scripts.logging import printStats
from elo import elo


def process_elo(start_year, end_year, SQL_Write, SQL_Read):
    teams = {}
    for team in SQL_Read.getTeams():
        teams[team.getNumber()] = team

    start, mean_reversion = elo.start_rating(), elo.mean_reversion()

    team_years_all = {}
    for year in range(start_year, end_year + 1):
        print(year)
        team_years = {}
        team_matches = {}
        team_elos = {}
        for teamYear in SQL_Read.getTeamYears(year=year):
            # eventually will need 2021 logic here
            num = teamYear.getTeam()
            team_years[num] = teamYear
            team_matches[num] = []
            elo_2yr = mean_reversion
            if year-2 in team_years_all and \
                    num in team_years_all[year-2] and \
                    team_years_all[year-2][num].elo_max is not None:
                elo_2yr = team_years_all[year-2][num].elo_max
            elo_1yr = mean_reversion
            if year-1 in team_years_all and \
                    num in team_years_all[year-1] and \
                    team_years_all[year-1][num].elo_max is not None:
                elo_1yr = team_years_all[year-1][num].elo_max
            start_rating = elo.existing_rating(elo_1yr, elo_2yr)
            team_elos[num] = start if year == 2002 else start_rating
            teamYear.elo_start = team_elos[num]
            # print(teamYear, teamYear.start_rating)

        correct, error = 0, 0
        matches = SQL_Read.getMatches_year(year=year)
        for match in matches:
            red, blue = match.getTeams()
            red_elo_pre = [team_elos[t] for t in red]
            blue_elo_pre = [team_elos[t] for t in blue]
            match.setRedEloPre(red_elo_pre)
            match.setBlueEloPre(blue_elo_pre)

            win_prob = elo.win_probability(red_elo_pre, blue_elo_pre)
            match.elo_win_prob = win_prob
            match.elo_winner = "red" if win_prob > 0.5 else "blue"

            red_elo_post, blue_elo_post = elo.update_rating(
                year, red_elo_pre, blue_elo_pre, match.red_score,
                match.blue_score, match.playoff)
            match.setRedEloPost(red_elo_post)
            match.setBlueEloPost(blue_elo_post)
            for i in range(len(red)):
                team_elos[red[i]] = red_elo_post[i]
                team_matches[red[i]].append(red_elo_post[i])
            for i in range(len(blue)):
                team_elos[blue[i]] = blue_elo_post[i]
                team_matches[blue[i]].append(blue_elo_post[i])

            if match.winner == match.elo_winner:
                correct += 1
            win_prob = 0.5
            if match.winner == "red":
                win_prob = 1
            elif match.winner == "blue":
                win_prob = 0
            error += (win_prob - match.elo_win_prob) ** 2

        acc = round(correct / len(matches), 4)
        mse = round(error / len(matches), 4)
        year_elos = []

        for team_event in SQL_Read.getTeamEvent_byParts(year=year):
            team_id = team_event.team_id
            data = sorted(team_event.matches)
            elos = [m.getTeamElo(team_id) for m in data]
            team_event.elo_start = elos[0]
            team_event.elo_end = elos[-1]
            team_event.elo_max = max(elos)
            team_event.elo_mean = sum(elos)/len(elos)
            team_event.elo_diff = elos[-1] - elos[0]
            elo_pre_playoffs = elos[0]
            for match in data:
                if match.comp_level == "qm":
                    elo_pre_playoffs = match.getTeamElo(team_id)
            team_event.elo_pre_playoffs = elo_pre_playoffs

        # all event elo stats based on pre-playoff elos
        for event in SQL_Read.getEvents_year(year=year):
            elos = []
            for team_event in event.team_events:
                elos.append(team_event.elo_pre_playoffs)
            elos.sort()
            event.elo_max = elos[0]
            event.elo_top8 = -1 if len(elos) < 8 else elos[7]
            event.elo_top24 = -1 if len(elos) < 24 else elos[23]
            event.elo_mean = round(sum(elos)/len(elos), 2)
            event.elo_sd = round(statistics.pstdev(elos), 2)

        for team in team_matches:
            elos = team_matches[team]
            if elos == []:
                SQL_Write.remove(team_years[team])
                team_years.pop(team)
            else:
                elo_max = max(elos[min(len(elos)-1, 8):])
                year_elos.append(elo_max)
                team_years[team].elo_max = elo_max
                team_years[team].elo_mean = round(sum(elos)/len(elos), 2)
                team_years[team].elo_end = team_elos[team]
                team_years[team].elo_diff = team_years[team].elo_end \
                    - team_years[team].elo_start

                pre_champs = -1
                for event in sorted(team_years[team].events):
                    # goes from team_event to event
                    if event.event.type < 3:
                        pre_champs = event.elo_end
                team_years[team].elo_pre_champs = pre_champs

        year_elos.sort()
        year_obj = SQL_Read.getYear(year=year)
        year_obj.elo_max = year_elos[0]
        year_obj.elo_1p = year_elos[round(0.01*len(year_elos))]
        year_obj.elo_5p = year_elos[round(0.05*len(year_elos))]
        year_obj.elo_10p = year_elos[round(0.10*len(year_elos))]
        year_obj.elo_25p = year_elos[round(0.25*len(year_elos))]
        year_obj.elo_median = (year_elos[round(0.50*len(year_elos))])
        year_obj.elo_mean = round(sum(year_elos)/len(year_elos), 2)
        year_obj.elo_sd = round(statistics.pstdev(year_elos), 2)
        year_obj.elo_acc = acc
        year_obj.elo_mse = mse

        team_years_all[year] = team_years

    for team in SQL_Read.getTeams():
        years = {}
        for year in team.team_years:
            years[year.year_id] = year.elo_max
        keys = years.keys()
        vals = years.values()
        recent = []
        for year in range(2017, end_year):
            if year in years:
                recent.append(years[year])
        r_y, y = len(recent), len(vals)
        team.elo = -1 if not team.active else years[max(keys)]

        '''
        temporary solution applying mean reversion if no 2020 matches
        '''
        if team.active and max(keys) == 2019:
            yr_1 = 1450 if 2019 not in years else years[2019]
            yr_2 = 1450 if 2018 not in years else years[2018]
            team.elo = 0.56 * yr_1 + 0.24 * yr_2 + 0.20 * 1450
        '''
        End temporary block
        '''

        team.elo_recent = -1 if r_y == 0 else round(sum(recent)/r_y, 2)
        team.elo_mean = -1 if y == 0 else round(sum(vals)/y, 2)
        team.elo_max = -1 if y == 0 else max(vals)

    SQL_Write.commit()

    '''
    DONE: Elo matches, Elo team years, Elo years, Elo teams
    TODO: Elo events, Elo team events
    '''


def test(start_year, end_year, SQL_Write, SQL_Read):
    return


def main(start_year, end_year, SQL_Write, SQL_Read):
    process_elo(start_year, end_year, SQL_Write, SQL_Read)
    test(start_year, end_year, SQL_Write, SQL_Read)
    printStats(SQL_Write=SQL_Write, SQL_Read=SQL_Read)
