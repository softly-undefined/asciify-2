new asciify plans

in asciify mk1 i was working with a controlled environment where each character had a fixed equivalent height and width, but now i want it to work with the default settings in a new google doc, with line spacing as single.

the unique aspect here is now each character doesnt have a set space that it takes up, more thin characters at the beginning of a line allow for more characters to fit into the line later on. I view this as a search algorithm, where there isnt a set number of characters per line (the minimum is the max number of the thickest character, the max is the max number of the thinnest character)

the overall idea is to divide the image into strips, and use a search algorithm to search for an optimal string to represent that horizontal strip. Optimal is defined by arithmetic distance between that strip and 

I will provide screenshots of each character (including the whitespace below the character, and to the right of the character before the next one begins) which should let you establish the width of each individual character.

one hyperparameter im concerned about tuning for each input image is "num_lines" which should range from 5 to the number of lines possible in one page (51). This impacts the thickness of each horizontal strip. I'm curious on how to improve this- for the first approach do this:

1. start at num_lines=5
2. select 5 random lines
3. run the search algorithm on these 5 lines, save the mean of the result
4. num_lines +=5
5. if num_lines =max(num_lines) continue, else goto 2
6. for each tuple (num_lines, mean result) divide mean result by num_lines
7. choose the highest of these values
8. run the search algorithm on the remaining lines for this chosen num_lines, save results!

In terms of the search algorithm, for the first attempt I want to use a beam search algorithm.

Work entirely in the asciify-mk2 folder.