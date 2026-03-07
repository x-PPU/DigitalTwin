a_acc=5.5 % rad/s^2
a_de=5.5% rad/s^2
m=0.5 % kg
l=0.2; % m
L=0.4; % m
Mass=2; % kg
I_R=Mass*(0.5*L)^2 % kg*m^2 
dot_phi_soll=1 % rad/s
%  tic
 sim('dynamik_3');
%  toc